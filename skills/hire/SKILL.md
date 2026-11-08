---
name: hire
description: Use when the owner asks to create or manage a companion bot in Herdr. Hire a new one with its own folder, identity and session, list them, change a companion's name or identity, or retire it. Triggers "hire", "contrata um bot", "cria um companheiro", "novo companheiro", "quais bots temos", "muda a identidade do bot", "aposenta o bot", "demite o bot". Only on the owner's request, never on the agent's own initiative. Not bili-agents (that opens and steers bots that already exist) and not a subagent (a companion persists, with its own Herdr workspace and session).
metadata:
  version: 0.1.0
  license: MIT
---

# hire

A companion is a persistent Claude session with its own folder and Herdr workspace, running on the owner's account.
Act only when the owner asked for this specific action. The human page is the [README](README.md); history is in the
[CHANGELOG](CHANGELOG.md).

## Hire

1. Draft the identity (`AGENTS.md`) from the request: who it is, what it answers for, what it must not do, and how it
   reports to the owner. Start from what the owner said; ask only what changes the identity.
2. Show the full identity and the chosen `id` and name through `AskUserQuestion`. Nothing is created before the ok.
3. Save the identity to a scratch file and run:

   ```sh
   scripts/hire.py new <id> "<Name>" --brief <file>
   ```

   The id is `a-z`, `0-9`, `_` or `-`, at most 32 characters. The folder defaults to `$AG_HOME/<id>`.
4. Confirm that the command printed a terminal address. The bot shows up in Bots within 5 seconds.

A refused `new` means the id, name or folder already exists. Pick another; never move or delete the folder to make room.

## List

`scripts/hire.py list`. `live` is true, false, or null when Herdr cannot be inspected.

## Update

Show the new identity to the owner first, then:

```sh
scripts/hire.py update <id> [--name "<Name>"] [--brief <file>]
```

The previous identity is kept in `<folder>/.hire/previous/`. A running session sees a new identity only after it
starts again; do not restart it without the owner's request.

## Retire

Retiring removes the bot from Bots. The folder and the conversation stay on disk. Name the bot and this consequence
in an `AskUserQuestion`, and only after a yes run:

```sh
scripts/hire.py retire <id> --confirm
```

A live terminal blocks retirement. The owner closes it; never kill or restart a session to get past this.

## The principal bot

Exactly one bot carries `"principal": true` in `bots.json`. It can never be retired, and its identity is maintained by
the owner, so `update --brief` refuses it. With zero or several principals, every write is refused. Report that to the
owner; never add, move or remove the mark to make a command pass.
