#!/usr/bin/env python3
"""The Pacific Park agent's set-up on a Grok Bot computer - fetched and run by the skill pacific-park-start-here at
the start of every Pacific Park conversation (28 Oct 2026). Standard library only; Python 3.8 or later.

What it does, every run, in ~/.pacpark/ (PACPARK_HOME to choose another folder):
  1. reads the keys file keys.env (the agent's read-only keys: the data store, SharePoint, Looker, Yellow Dog; the
     person's address as PACPARK_USER) - stops with NEEDS INPUT when it is not there;
  2. brings the skills up to date from the agent's data store: the store's main build publishes every skill as one
     zip (agent_data/plugins/, labor_export.publish_plugins) with the Project's instruction box beside them; only a
     zip whose fingerprint changed is downloaded again, so a run after a push to main carries that push and a run
     with nothing new downloads nothing. Read with the store's key through raw.githubusercontent.com at the commit
     git's own branch list names - no request against GitHub's hourly API limit;
  3. writes the key files where the skills read them (park-data/credentials/*.env, yellowdog/credentials/);
  4. installs the Python packages the skills need, when missing (lost after a Grok Bot computer update);
  5. downloads today's copy of the agent's SharePoint folder with the read key through park-data's own reader:
     state/, knowledge/ (not its assets) and corrections/ (not its folded/ trail) into sharepoint/;
  6. writes START.md: this channel's note (channel.md, fetched from the plugin's repository), the instruction box,
     and what to read next.
Nothing here writes to SharePoint, the store or GitHub. No key is ever printed.

Exit codes: 0 done; 66 an input is missing (one NEEDS INPUT line says which); 1 something else failed (said).
"""
import base64
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile

HOME = os.environ.get("PACPARK_HOME") or os.path.join(os.path.expanduser("~"), ".pacpark")
KEYS = os.path.join(HOME, "keys.env")
SKILLS = os.path.join(HOME, "skills")
SHAREPOINT = os.path.join(HOME, "sharepoint")
START = os.path.join(HOME, "START.md")
MARKER = os.path.join(SKILLS, ".from.json")
PUBLIC = "https://raw.githubusercontent.com/EllisClaude/pacpark-grokbot/main"   # the plugin's own files, no key needed
RAW = "https://raw.githubusercontent.com"
DEFAULT_REPO = "EllisClaude/pacpark-agent-data"
REQUIRED = ("PACPARK_GITHUB_TOKEN", "GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")
# module to import -> package to install (the skills' needs: park-data, monitor, board-deck, slide-reader, pnl)
PACKAGES = (("pandas", "pandas"), ("numpy", "numpy"), ("openpyxl", "openpyxl"), ("pptx", "python-pptx"),
            ("lxml", "lxml"), ("PIL", "Pillow"), ("fitz", "pymupdf"), ("requests", "requests"), ("yaml", "pyyaml"),
            ("sklearn", "scikit-learn"), ("statsmodels", "statsmodels"), ("tabulate", "tabulate"), ("xlrd", "xlrd"),
            ("pdfplumber", "pdfplumber"))
# the key files inside the skills -> the variables each holds (the files the skills' scripts look for)
KEY_FILES = (("park-data/credentials/github-read.env", ("PACPARK_GITHUB_TOKEN", "PACPARK_DATA_REPO")),
             ("park-data/credentials/sharepoint-app.env", ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")),
             ("park-data/credentials/looker.env", ("LOOKER_HOST", "LOOKER_CLIENT_ID", "LOOKER_CLIENT_SECRET")),
             ("park-data/credentials/axper.env", ("AXPER_API_KEY",)),
             ("yellowdog/credentials/yellowdog.env", ("YD_USER", "YD_PASS", "YD_CLIENT_ID")))
# the agent's SharePoint folder: (folder, subfolders not entered)
SP_FOLDERS = (("state", ()), ("knowledge", ("assets",)), ("corrections", ("folded",)))
SP_TEXT = (".md", ".txt", ".csv", ".json")


def say(msg: str) -> None:
    print(msg, flush=True)


def needs(msg: str) -> None:
    print("NEEDS INPUT: " + msg, flush=True)
    sys.exit(66)


def read_keys() -> dict:
    if not os.path.isfile(KEYS):
        needs(f"the keys file {KEYS} - the agent's read-only keys. Ask the person to attach pacpark-keys.env (Bruno "
              f"Dyjas sent it to them), save it as {KEYS}, then run this program again.")
    vals = {}
    with open(KEYS, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    missing = [k for k in REQUIRED if not vals.get(k)]
    if missing:
        needs(f"{', '.join(missing)} in {KEYS} - the keys file is incomplete. Ask Bruno Dyjas for a fresh pacpark-keys.env.")
    vals.setdefault("PACPARK_DATA_REPO", DEFAULT_REPO)
    if not vals.get("PACPARK_USER"):                     # one key file for everyone: the person names themselves once
        u = os.path.join(HOME, "user.txt")               # (the Bot writes ~/.pacpark/user.txt from the set-up message)
        if os.path.isfile(u):
            with open(u, encoding="utf-8-sig") as fh:
                lines = [l.strip() for l in fh.read().splitlines() if l.strip()]
            vals["PACPARK_USER"] = lines[0] if lines else ""
    try:
        os.chmod(KEYS, 0o600)
    except OSError:
        pass
    return vals


def http_get(url: str, token: str = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pacpark-setup"})
    if token:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"x-access-token:{token}".encode()).decode())
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def store_commit(repo: str, token: str) -> str:
    """The store's main commit from git's own branch list (what a `git fetch` reads first; no API request)."""
    try:
        data = http_get(f"https://github.com/{repo}.git/info/refs?service=git-upload-pack", token).decode("utf-8", "replace")
        m = re.search(r"([0-9a-f]{40}) refs/heads/main\b", data)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "main"


def refresh_skills(vals: dict):
    """The skills from the store's plugins section: only what changed is downloaded. Returns (commit, fresh, kept)."""
    repo, token = vals["PACPARK_DATA_REPO"], vals["PACPARK_GITHUB_TOKEN"]
    commit = store_commit(repo, token)
    try:
        manifest = json.loads(http_get(f"{RAW}/{repo}/{commit}/agent_data/manifest.json", token).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            needs(f"a working store key - GitHub answered HTTP {e.code} for the agent's data store ({repo}) with the "
                  f"key in {KEYS}. Ask Bruno Dyjas for a fresh pacpark-keys.env.")
        raise
    sec = manifest.get("plugins") or {}
    files = sec.get("files") or {}
    if not files:
        say("the store holds no skills yet (its next build publishes them); the skills already here are kept")
        return commit, 0, 0
    have = {}
    if os.path.isfile(MARKER):
        try:
            with open(MARKER, encoding="utf-8") as fh:
                have = json.load(fh)
        except Exception:
            have = {}
    os.makedirs(SKILLS, exist_ok=True)
    fresh = kept = 0
    for rel in sorted(files):
        sha = files[rel]["sha256"]
        name = os.path.basename(rel)
        target = os.path.join(SKILLS, name[:-4] if name.endswith(".zip") else name)
        if have.get(rel) == sha and os.path.exists(target):
            kept += 1
            continue
        data = http_get(f"{RAW}/{repo}/{commit}/agent_data/{rel}", token)
        if hashlib.sha256(data).hexdigest() != sha:
            raise SystemExit(f"{rel}: the download does not match the store's manifest (a build in progress?) - run again")
        if name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for n in z.namelist():
                    if n.startswith("/") or ".." in n.split("/"):
                        raise SystemExit(f"{rel}: a file name that leaves the folder ({n!r}) - not unpacked")
                shutil.rmtree(target, ignore_errors=True)
                z.extractall(SKILLS)
        else:
            with open(target, "wb") as fh:
                fh.write(data)
        have[rel] = sha
        fresh += 1
    for rel in list(have):                                      # a skill gone from main is gone from here
        if rel not in files:
            name = os.path.basename(rel)
            t = os.path.join(SKILLS, name[:-4] if name.endswith(".zip") else name)
            if os.path.isdir(t):
                shutil.rmtree(t, ignore_errors=True)
            elif os.path.isfile(t):
                os.remove(t)
            have.pop(rel)
    with open(MARKER, "w", encoding="utf-8") as fh:
        json.dump(have, fh, indent=1)
    return commit, fresh, kept


def write_keys(vals: dict) -> list:
    written = []
    for rel, names in KEY_FILES:
        skill = rel.split("/")[0]
        if not os.path.isdir(os.path.join(SKILLS, skill)):
            continue
        present = [n for n in names if vals.get(n)]
        if not present:
            continue
        p = os.path.join(SKILLS, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            for n in present:
                fh.write(f"{n}={vals[n]}\n")
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
        written.append(rel)
    return written


def packages() -> str:
    missing = [pkg for mod, pkg in PACKAGES if importlib.util.find_spec(mod) is None]
    if not missing:
        return "Python packages: all present"
    say(f"installing Python packages: {' '.join(missing)} (a minute or two)")
    base = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    last = ""
    for extra in (["--user"], [], ["--user", "--break-system-packages"], ["--break-system-packages"]):
        r = subprocess.run(base + extra + missing, capture_output=True, text=True)
        if r.returncode == 0:
            # a fresh interpreter sees what pip just installed (this one's import paths were set at its start)
            probe = ("import importlib.util,sys; print(' '.join(p for m,p in %r if importlib.util.find_spec(m) is None))"
                     % (list(PACKAGES),))
            r2 = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
            still = r2.stdout.split() if r2.returncode == 0 else []
            return "Python packages installed: " + " ".join(missing) + (f" (still missing: {' '.join(still)})" if still else "")
        last = (r.stderr or r.stdout).strip()[-400:]
    return "some Python packages could not be installed: " + " ".join(missing) + " - pip said: " + last


def sharepoint_copy(vals: dict) -> int:
    scripts = os.path.join(SKILLS, "park-data", "scripts")
    if not os.path.isfile(os.path.join(scripts, "sharepoint_reader.py")):
        say("park-data is not here yet: the knowledge files wait for the store's next build")
        return 0
    for k in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"):
        os.environ[k] = vals[k]
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import sharepoint_reader as sr
    reader = sr.Reader()
    fresh = SHAREPOINT + f".new-{os.getpid()}"
    shutil.rmtree(fresh, ignore_errors=True)
    n = 0
    for folder, skip in SP_FOLDERS:
        for e in reader.walk(folder, depth=1, skip=skip):
            if not e["name"].lower().endswith(SP_TEXT):
                continue
            reader.download("id:" + e["id"], os.path.join(fresh, folder, *e["path"].split("/")))
            n += 1
    shutil.rmtree(SHAREPOINT, ignore_errors=True)
    os.replace(fresh, SHAREPOINT)
    return n


FONTS_URL = "https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz"


def fonts() -> str:
    """Liberation Sans - Arial's character widths - for the deck skills' text measure, in the user's own font folder
    (a Grok Bot computer has no administrator rights, so the system folders the skills look in first stay empty):
    ~/.fonts/liberation/LiberationSans-{Regular,Bold}.ttf and the same files as ~/.fonts/msttcorefonts/arial{,bd}.ttf,
    which is how the release workflow names them. Windows has Arial; a system Liberation is used as it is."""
    if os.name == "nt":
        return ""
    home = os.path.expanduser("~")
    lib = os.path.join(home, ".fonts", "liberation")
    ms = os.path.join(home, ".fonts", "msttcorefonts")
    if os.path.isfile(os.path.join(ms, "arial.ttf")) and os.path.isfile(os.path.join(lib, "LiberationSans-Bold.ttf")):
        return "fonts: present"
    import tarfile
    try:
        data = http_get(FONTS_URL)
        os.makedirs(lib, exist_ok=True)
        os.makedirs(ms, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            for m in t.getmembers():
                base = os.path.basename(m.name)
                if base in ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf") and m.isfile():
                    body = t.extractfile(m).read()
                    with open(os.path.join(lib, base), "wb") as fh:
                        fh.write(body)
                    with open(os.path.join(ms, "arialbd.ttf" if "Bold" in base else "arial.ttf"), "wb") as fh:
                        fh.write(body)
        return "fonts: Liberation Sans fetched (Arial's widths) for the deck skills' text measure"
    except Exception as e:
        return f"fonts: not fetched ({type(e).__name__}); the deck skills measure text at half an em a character"


def channel_note() -> str:
    stored = os.path.join(SKILLS, "channel.md")                # the store's copy, from main, beside the skills
    if os.path.isfile(stored):
        with open(stored, encoding="utf-8") as fh:
            return fh.read()
    cached = os.path.join(HOME, "channel.md")
    try:
        text = http_get(f"{PUBLIC}/channel.md").decode("utf-8")
        with open(cached, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return text
    except Exception:
        if os.path.isfile(cached):
            with open(cached, encoding="utf-8") as fh:
                return fh.read()
        return "# You are answering in Grok Bot\n\n(the channel note could not be fetched; follow the instructions below)\n"


def instruction_box() -> str:
    p = os.path.join(SKILLS, "project-instructions.md")
    if not os.path.isfile(p):
        return "(the instruction box is not in the store yet: its next build publishes it)\n"
    with open(p, encoding="utf-8") as fh:
        text = fh.read()
    i = text.find("\n---\n")                        # the repo header above the line is not the box
    return text[i + 5:] if i >= 0 else text


def _lock():
    """One set-up at a time on this computer (several Bots share ~/.pacpark): a second run waits for the first."""
    os.makedirs(HOME, exist_ok=True)
    try:
        import fcntl
    except ImportError:                               # not Linux: no lock
        return None
    fh = open(os.path.join(HOME, ".lock"), "w")
    fcntl.flock(fh, fcntl.LOCK_EX)
    return fh


def self_refresh() -> str:
    """The store carries this program too (agent_data/plugins/setup.py, from main): when it differs from the running
    copy, the running copy is replaced for the NEXT run, so a change on main reaches every Bot without the plugin.
    Only a copy that lives in HOME is replaced - never a checkout's file or another folder's."""
    stored = os.path.join(SKILLS, "setup.py")
    me = os.path.realpath(os.path.abspath(__file__))
    home = os.path.realpath(HOME)
    if not me.startswith(home.rstrip(os.sep) + os.sep) or not os.path.isfile(stored):
        return ""
    try:
        with open(stored, "rb") as a, open(me, "rb") as b:
            if a.read() == b.read():
                return ""
        shutil.copyfile(stored, me)
        return "the set-up program itself was updated from the store (used from the next run)"
    except OSError as e:
        return f"the set-up program could not update itself: {e}"


def main() -> int:
    lock = _lock()
    vals = read_keys()
    person = vals.get("PACPARK_USER") or "not named in the keys file"
    commit, fresh, kept = refresh_skills(vals)
    skills = sorted(d for d in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, d))) if os.path.isdir(SKILLS) else []
    say(f"skills: {len(skills)} in {SKILLS} (store build {commit[:7]}; {fresh} refreshed, {kept} unchanged)")
    keys = write_keys(vals)
    say(f"key files written inside the skills: {len(keys)}")
    note = self_refresh()
    if note:
        say(note)
    say(packages())
    f = fonts()
    if f:
        say(f)
    n = sharepoint_copy(vals)
    say(f"SharePoint copy: {n} files in {SHAREPOINT} (state, knowledge, corrections)")
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    head = (f"# Pacific Park agent - read this first\n\n"
            f"Made by the set-up program on {now}. Person you work for: {person}.\n"
            f"Skills: {SKILLS} ({len(skills)} skills, store build {commit[:7]}). "
            f"SharePoint copy: {SHAREPOINT} ({n} files, downloaded now).\n\n"
            f"Read next, whole, in this order: `{SHAREPOINT}/state/project-state.md`, then "
            f"`{SHAREPOINT}/knowledge/instructions.md`, then every knowledge file it lists (all in "
            f"`{SHAREPOINT}/knowledge/`). List `{SHAREPOINT}/corrections/` before any factual answer. Then the "
            f"person's question.\n\n---\n\n")
    with open(START, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + channel_note().rstrip() + "\n\n---\n\n" + instruction_box().rstrip() + "\n")
    say(f"START.md written: {START} - read it whole now, then the files it names.")
    del lock
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:                            # a plain line, never a traceback with a key in it
        print(f"the set-up failed: {type(e).__name__}: {str(e)[:300]}", flush=True)
        sys.exit(1)
