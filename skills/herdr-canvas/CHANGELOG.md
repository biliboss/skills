# Changelog

## 0.1.1

- Documentation only, no code change: `## Next step` in `SKILL.md` notes the plan (not implemented) to render `canvas/page.html` in a WKWebView through `herdr.nativeView` (fork with the nativeView patch, issue #425), falling back to `canvas/page.md`.

## 0.1.0

- First version: `canvas publish|comments|resolve|open|install` and the Herdr Canvas panel (`apps/herdr-canvas`): the bot's `canvas/page.md` in numbered blocks, one comment per block, Enter sends it to the bot's terminal with `hc send --if idle`.
- Installing and publishing never move focus; only `canvas open` talks to the Herdr window, and only when the owner asks.
