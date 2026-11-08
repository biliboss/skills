# herdr-canvas

A Herdr panel (beside Files and Changes) that shows a bot's `canvas/page.md` in numbered blocks. The owner clicks a block, types, presses Enter; the comment goes to `<bot>/canvas/comments.jsonl` and `comments.md`, and the bot gets a `hc send`.

- Mod and installer: `../../apps/herdr-canvas/`. CLI: `scripts/canvas`. Link it: `ln -s <repo>/skills/herdr-canvas/scripts/canvas ~/.local/bin/canvas`.
- Herdr config folder: the variable is `HERDR_APP_HOME` (not `HERDR_HOME`). Unset, the installer uses `~/.config/herdr-app` and prints it.
- The mod loads when the owner first opens the panel or restarts Herdr. Installing opens nothing.
- Fallback for rich text: see `../../apps/herdr-canvas/README.md` (plain text per block).
- `canvas publish <bot> <file.html>` writes `canvas/page.html`. On the Herdr Bili build (v0.1.14+, `herdr.nativeView`) the panel shows it as a page; comments need the `page.md` twin (toggle Página/Blocos in the header). Official Herdr ignores page.html and shows the Markdown panel.
