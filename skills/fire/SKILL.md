---
name: fire
description: Use when the owner asks to remove a companion bot from Herdr. Triggers "fire", "demite o bot", "aposenta o bot", "remove o companheiro". Only on the owner's explicit request for that bot. Not rebrief (changes it) and not for closing a session.
metadata:
  version: 0.1.0
  license: MIT
---

# fire

Firing removes the bot from Bots. Its folder and conversation stay on disk.

1. Name the bot and this consequence in an `AskUserQuestion`.
2. Only after a yes, run `scripts/fire <id> --confirm`.

A live terminal blocks this. The owner closes it; never kill or restart a session to get past it.

The bot marked `"principal": true` in `bots.json` can never be fired. With zero or several principals every removal is
refused. Report that to the owner; never add, move or remove the mark to make a command pass.

Details: [README](README.md), [CHANGELOG](CHANGELOG.md).
