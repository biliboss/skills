---
name: rebrief
description: Use when the owner asks to change a companion bot's name or identity in Herdr. Triggers "rebrief", "muda a identidade do bot", "renomeia o bot", "ajusta o companheiro". Only on the owner's request. Not hire (creates) nor fire (removes).
metadata:
  version: 0.1.0
  license: MIT
---

# rebrief

1. Show the new identity to the owner through `AskUserQuestion`. Nothing changes before the ok.
2. Run `scripts/rebrief <id> [--name "<Name>"] [--brief <file>]`.

The previous identity is kept in `<folder>/.hire/previous/`. A running session sees a new identity only after it starts
again; do not restart it without the owner's request.

The principal bot can be renamed, but its identity is maintained by the owner, so `--brief` refuses it.

Details: [README](README.md), [CHANGELOG](CHANGELOG.md).
