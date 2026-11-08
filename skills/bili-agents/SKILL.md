---
name: bili-agents
description: Open or focus local bots in Herdr through the ag-* tools. Use for a bot registry, dedicated hidden bot workspaces, and explicit session creation or resumption.
metadata:
  version: 0.2.4
---

# Bots in Herdr

Read `../../apps/herdr-bots/README.md` before installation. The code belongs in this repository; personal bot folders,
commands and UUIDs belong in `$AG_HOME/bots.json` (default `~/agents/bots.json`), outside this repository.

- `scripts/ag-open --list`: validate and print the registry, including derived workspace IDs.
- `scripts/ag-open <id>`: focus the existing terminal or open the bot in its dedicated workspace.
  Bot workspaces are hidden from Spaces, accessible through Bots. They never reuse a project workspace.
- `scripts/ag-bot-session <id>`: internal launcher; create with `--session-id`, then explicitly `--resume`.
  Never use `--continue` or silently fall back to a new conversation.
- `../../apps/herdr-bots/install.sh`: clone the active layout and Spaces mod, install Bots below the brand.
  `--bot ID NAME FOLDER UUID` also preserves an old instance in a dated backup and prepares an empty one.

Inspect live sessions before operating them. Do not send prompts, stop another session or move its files.
Preparation refuses any process using the target folder. Automatic Claude memory is disabled to avoid reusing a path’s older memory. Existing authentication remains available;
these tools inject no role, memory, hooks or settings. Claude's normal user-wide configuration still applies.
Keep legacy agent tooling separate from bot launch: it may inject roles and hooks.

Verify with `python3 scripts/test_bots.py`, `herdr-app check ../../apps/herdr-bots`, and a screenshot from the app.
Do not restart the user's Herdr to test persistence; inspect the saved personal layout and state instead,
and report that a real restart has not been exercised.
