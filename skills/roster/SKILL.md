---
name: roster
description: Use when the owner asks which companion bots exist in Herdr or whether one is running. Triggers "roster", "quais bots temos", "lista os companheiros", "o time de bots". Read-only. Not bili-agents' ag-open, which opens a bot.
metadata:
  version: 0.1.0
  license: MIT
---

# roster

Run `scripts/roster`. It prints JSON with each bot's `id`, `name`, `folder`, `principal`, `live` and `listeners`
(the ids of the bots that listen to it, read from its project settings; see the listen skill).

`live` is true, false, or null when Herdr cannot be inspected; report null as unknown, not as stopped.

Details: [README](README.md), [CHANGELOG](CHANGELOG.md).
