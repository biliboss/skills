# herdr-canvas

A Herdr right-panel option (beside Files, Changes and Browser) that shows a bot's `canvas/page.html`, a daisyUI page generated from Markdown or HTML blocks. The owner clicks "comentar" on a block; the comment goes to `<bot>/canvas/comments.jsonl` and `comments.md`, and the bot gets a `hc send`.

- Mod and installer: `../../apps/herdr-canvas/`. CLI: `scripts/canvas` (publish, show, set, append, remove, comments, resolve, serve, open, install). Link it: `ln -s <repo>/skills/herdr-canvas/scripts/canvas ~/.local/bin/canvas`.
- `page.html` is derived; edit through the verbs, which keep block ids stable and bump `canvas/version`.
- `canvas serve` is a local 127.0.0.1 server (stdlib only) for the page and its comments; see `SKILL.md` for the checks.
- Install: `HERDR_APP_HOME` is required (breaking since 0.3.0). The installer also patches `mods/tabs/main.js` to add the Canvas button.
- Official Herdr keeps the Markdown Blocos panel for md sources only.
