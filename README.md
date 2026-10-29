# Pacific Park agent, for Grok Bot

The Pacific Park agent, run as a Bot in Grok Bot. This plugin holds one skill, "Pacific Park agent - start here". It carries no facts about the Park, no keys and none of the agent's skills: at the start of every Pacific Park conversation it brings the skills up to date from the agent's data store, reads the knowledge files from SharePoint with the agent's read key, and gives the Bot its instructions. A change Bruno pushes to the agent's repository is live at the next conversation; nothing is re-installed.

## Set up, once

1. In Grok Bot open **Settings**, then **Plugins**, paste `https://github.com/EllisClaude/pacpark-grokbot` into the search box and add it.
2. Attach the key file Bruno sent you (`pacpark-keys.env`) to a chat with your Bot and tell it: "Save this as ~/.pacpark/keys.env and keep it there. Save my e-mail address as ~/.pacpark/user.txt (ask me if you do not know it)."
3. Tell the Bot once: "Remember: for anything about Pacific Park, run the skill pacific-park-start-here first, before answering, on your own cloud computer, never on my computer." (If the Bot ever asks to run a command on your own computer, answer Never: everything runs on its cloud computer.)

Then ask your questions about the Park. The first answer takes a minute or two longer (the skills and their packages are downloaded once).

## What is where

- `skills/pacific-park-start-here/SKILL.md`: the skill.
- `scripts/setup.py`: the set-up program the skill fetches and runs on the Bot's computer.
- `channel.md`: the note on how this channel works, shown to the Bot in front of the agent's instructions.
- `rules/pacific-park.md`: an always-on rule that points Pacific Park conversations at the skill.

The master copy of these files is `pacific-park/grokbot/` in SC's CirkulAgent repository; this repository is its published copy.
