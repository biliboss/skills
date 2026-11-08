# Changelog

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
