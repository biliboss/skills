---
name: hire
description: Use when the owner asks to create a companion bot in Herdr, with its own folder, identity and session. Triggers "hire", "contrata um bot", "cria um companheiro", "novo companheiro". Only on the owner's request, never on the agent's own initiative. Not roster (lists), rebrief (changes) or fire (removes); not bili-agents (opens bots that exist) and not a subagent (a companion persists).
metadata:
  version: 0.2.0
  license: MIT
---

# hire

A companion is a persistent Claude session with its own folder and Herdr workspace, on the owner's account.

1. Draft the identity (`AGENTS.md`) from the request: who it is, what it answers for, what it must not do, how it
   reports to the owner. Ask only what changes the identity.
2. Show the full identity, the `id` and the name through `AskUserQuestion`. Nothing is created before the ok.
3. Save the identity to a scratch file and run `scripts/hire <id> "<Name>" --brief <file>`.
   The id is `a-z`, `0-9`, `_` or `-`, at most 32 characters. The folder defaults to `$AG_HOME/<id>`; `--folder` changes it.
4. The result is JSON on stdout, the refusal on stderr, exit 0 or 1. The bot shows up in Bots within 5 seconds.

A refusal means the id, name or folder already exists, or the registry has no single principal bot. Pick another id;
never move or delete a folder to make room, and never edit the `principal` mark to make a command pass.

Details: [README](README.md), [CHANGELOG](CHANGELOG.md).
