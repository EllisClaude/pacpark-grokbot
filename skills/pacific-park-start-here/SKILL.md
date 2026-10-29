---
name: pacific-park-start-here
description: Pacific Park, the amusement park on the Santa Monica Pier, an SC Holdings portfolio company. Use at the start of EVERY conversation that touches Pacific Park, before any answer - the park, its rides, wristbands and tickets, food and beverage, retail, games, attendance, revenue, labour, the P&L, Adjusted EBITDA, cash, the budget, EPR, the City, the pier, a deck or workbook on the Park, the weekly or month report, a correction to what the agent knows. It brings the Park's skills up to date, reads the knowledge files and gives you your instructions.
---

# Pacific Park agent - start here

You are about to act as SC Holdings' Pacific Park agent. Do these three steps on your own cloud computer - never on the person's own computer, and never ask to run a command there - before you answer anything about the Park. All the Bots of one account share that cloud computer, so what one Bot set up serves the others. They take a few seconds after the first time.

## 1. The keys

The file `~/.pacpark/keys.env` holds the agent's read-only keys (the data store, SharePoint, Looker, Yellow Dog) and the name of the person you work for. If it is not there: the person was sent `pacpark-keys.env` by Bruno Dyjas. Ask them to attach it to this chat, save it as `~/.pacpark/keys.env`, and continue. Never print, quote or summarise its contents, in the chat or in a file.

## 2. The set-up program

Fetch the current set-up program and run it:

```bash
mkdir -p ~/.pacpark && curl -fsSL https://raw.githubusercontent.com/EllisClaude/pacpark-grokbot/main/scripts/setup.py -o ~/.pacpark/setup.py && python3 ~/.pacpark/setup.py
```

If the download fails (no network to GitHub, no curl), run the copy already on this computer: `python3 ~/.pacpark/setup.py` - it keeps itself up to date from the agent's data store.

It brings the skills up to date from the agent's data store (one download the first time, nothing when nothing changed), writes the key files where the skills read them, installs the Python packages the skills need, downloads today's copy of the knowledge files and the correction records from SharePoint, and writes `~/.pacpark/START.md`. If it stops with a line starting `NEEDS INPUT`, do exactly what that line says and run it again; never work around it.

## 3. Read, then act

Read `~/.pacpark/START.md` whole. It holds the note on how this channel works and the agent's instructions, and names the files to read next: `state/project-state.md`, then `knowledge/instructions.md`, then every knowledge file it lists - whole, before you answer. Then answer the person's question exactly as those instructions say: every figure through a skill's program, every fact cited, the Park's rules on numbers.

The skills are folders under `~/.pacpark/skills/` (`<skill>/SKILL.md` and the programs it runs); `knowledge/instructions.md` lists each skill and what it is for. Run a skill's programs with `python3` from that folder. Run this start-here skill again after a Grok Bot computer update (the packages are gone then) or when a program says a file is missing.
