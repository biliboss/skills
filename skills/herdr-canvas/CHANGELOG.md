# Changelog

## 0.4.0

- Comment mode with outline. The per-block "comentar" button and the notes under the blocks are gone: the page is clean and shows only a "Comentar" toggle (top right, key `c`). With the mode on, the block under the mouse is outlined with its id; a click opens a popover (Enter sends, Shift+Enter breaks the line, Esc closes the popover, then leaves the mode). Links do not navigate in the mode. The mode survives a reload (sessionStorage); without the server there is no toggle.
- The target is the block plus a `TextQuoteSelector {exact, prefix, suffix}` from the selection or the phrase under the click (`caretRangeFromPoint`, fallback `caretPositionFromPoint`; 120 chars, 32 of context). `POST /<bot>/comments` accepts an optional `quote`; it is validated, spaces are collapsed, and it is used only if `exact` is in the block's rendered text (so `**bold**`, links and code still match) or in its source; otherwise the selector stays the start of the block. A malformed quote never fails the post.
- Pins: with the mode on, every block with open comments shows a count; clicking opens a read-only list. The page receives only open comments (`id`, `blockId`, `body`, `quote`); a post updates the pins without reload.
- The page script moved to `scripts/page.js` (pure functions exported for `node --test`). The CSS was written by hand into `canvas.css` and `canvas.src.css` (daisyUI variables), not recompiled.

## 0.3.2

- Fix: the local server now comes up with the data, not with the first render. The mod's `reload()` calls `prepareWeb` when `wantsServer({hasHtml, caps})` (page.html and native web view); before, only `render()` did, so a Herdr window on another Space never started it. `prepareWeb` stays idempotent and render keeps the call as a safeguard. Without the native API nothing starts.
- `canvas open <bot>` ensures the server (same routine as `serve --detach`) before the two `layout.*` calls; a failure does not stop the open and is reported in the JSON field `server`. `serve --detach` refuses a bad `CANVAS_PORT` at once.

## 0.3.1

- Fix: the comment now reaches a bot that finished its turn. `hc send --if` takes one exact status and a bot parked at the prompt is `done`, so `--if idle` refused with `status_mismatch`. Each attempt now reads `hc get <addr> --json` (`status.state`) and, when it is idle or done, runs `hc send <addr> <text>` without `--if`; working, blocked, any other state or a failed read counts as a refusal and follows the same retry (20 s, 3 times) and `notify.log`. Never `--force`. Same in `apps/herdr-canvas/mod/notify.js` and `canvaslib.py`.

## 0.3.0

- BREAKING (install): `install.py` requires `HERDR_APP_HOME` and refuses without it. It now also patches `mods/tabs/main.js` (Canvas button in the right panel next to Browser), idempotent, with backup and a clear error if the anchor is missing.
- `page.html` is always derived, with Tailwind + daisyUI compiled once and vendored (`apps/herdr-canvas/vendor`), light and dark, inline, no CDN. `.md` publishes keep `page.md`; `.html` publishes are split into `canvas/blocks/`.
- New verbs `show`, `set`, `append`, `remove` with block ids equal to the JS mod's; every verb rewrites `page.html` and bumps `version` atomically.
- New `canvas serve [--detach|--stop]`: 127.0.0.1 only, token, Origin/Host/Content-Type/size checks, writes comments and notifies the bot like the mod does.
- Mod: shows the page from the server (trust interactive) so comments work inside the HTML; falls back to the file (static). Starts the server with `herdr.exec`.
- `canvas open` now runs `layout.select --child canvas` then `layout.show --id panel` with the home from `CANVAS_HERDR_HOME`; no split, no focus.
- Not verified on a real window.

## 0.2.2

- Mod: native view id is unique per panel; two panels on the same bot no longer erase each other's view.

## 0.2.1

- Mod: the native view gets an explicit size (`w_full`, `flex_1`, `min_h(0)`) inside a flex column, as the fork's real example does.

## 0.2.0

- `canvas publish` accepts `.html` (writes `canvas/page.html`); `.md` unchanged; both coexist.
- Mod: with `page.html`, `herdr.nativeView` and `web` in `nativeViewCapabilities()` (Herdr Bili build), the page shows in a native view; otherwise the Markdown panel as before. "Página"/"Blocos" toggle when `page.md` also exists, one-line footer note when it does not. Decision in `mod/pagemode.js` (pure, tested). Detection is defensive, so official Herdr still loads the mod. Never calls the view `focus` action.
- Not verified in a real window.

## 0.1.1

- Documentation only, no code change: `## Next step` in `SKILL.md` notes the plan (not implemented) to render `canvas/page.html` in a WKWebView through `herdr.nativeView` (fork with the nativeView patch, issue #425), falling back to `canvas/page.md`.

## 0.1.0

- First version: `canvas publish|comments|resolve|open|install` and the Herdr Canvas panel (`apps/herdr-canvas`): the bot's `canvas/page.md` in numbered blocks, one comment per block, Enter sends it to the bot's terminal with `hc send --if idle`.
- Installing and publishing never move focus; only `canvas open` talks to the Herdr window, and only when the owner asks.
