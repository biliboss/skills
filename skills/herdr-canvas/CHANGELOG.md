# Changelog

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
