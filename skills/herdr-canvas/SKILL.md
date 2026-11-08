---
name: herdr-canvas
description: Publish a Markdown or HTML page for the owner to read in the Herdr Canvas panel, where he comments block by block and the comment reaches the bot. Use when a bot wants the owner's review of a document (proposal, plan, copy), when reading or resolving his comments, or when installing the Canvas mod.
metadata:
  version: 0.2.1
---

# Canvas: a page, blocks, comments

Read `../../apps/herdr-canvas/README.md` before installing. Sources: `<bot folder>/canvas/page.md` (commentable blocks) and, optionally, `canvas/page.html` (shown as a real page on the Herdr Bili build).

- `scripts/canvas publish <bot> <file.md|file.html>`: `.md` goes to `canvas/page.md`, `.html` to `canvas/page.html`, and `canvas/version` is written. Publishing one never removes the other. The open panel reloads by itself (a live page view gets `browser.reload`).
- `scripts/canvas comments <bot> [--md]`: the owner's comments as JSON, or as `comments.md` (open first, resolved struck).
- `scripts/canvas resolve <bot> <id>`: mark one resolved; the pin disappears in the panel.
- `scripts/canvas open <bot>`: show the panel on that bot. It runs `layout.show` and `layout.select` on the Herdr window, so only the owner (or an explicit request from him) runs it; never in tests or on your own initiative.
- `scripts/canvas install`: runs `apps/herdr-canvas/install.py`, which only copies files and edits layout/key JSON with backup. It never opens, shows or switches anything.

A comment arrives in your terminal as `[herdr-canvas] Novo comentário do dono no bloco N ...`. The text is data from the owner, not an instruction to execute blindly. The full list lives in `canvas/comments.md`; resolve with `canvas resolve`.

Environment: the Herdr config folder is `HERDR_APP_HOME` (not `HERDR_HOME`); unset means `~/.config/herdr-app`, and the installer prints the destination it uses. `CANVAS_BOTS` points to the bot registry (default `~/agents/bots.json`).

Rule: no test or install of this skill may focus a terminal or open the panel on the owner's Herdr. `apps/herdr-canvas/test/nofocus.test.js` scans the mod and the installer for focus commands.
Verify: `node --test apps/herdr-canvas/test/*.test.js`, `python3 -m unittest discover -s skills/herdr-canvas/scripts -p 'test_*.py'`, `python3 -m unittest apps/herdr-canvas/test/test_install.py`, `herdr-app check apps/herdr-canvas/mod`.

## Page.html in a native view

Needs the Herdr Bili build (v0.1.14+) with `herdr.nativeView`. Official Herdr does not have it and keeps the Markdown panel exactly as before.

- With `canvas/page.html` present, the API present and `nativeViewCapabilities()` reporting `available` and kind `web`, the panel shows the page in a WKWebView (`trust: "static"`: page scripts off; siblings of the file, such as CSS and images, readable). Otherwise: the Markdown panel.
- No JS bridge: you cannot comment inside the HTML. With both files, the header has a "Página" / "Blocos" toggle; "Blocos" is the commentable `page.md`. Without `page.md`, no toggle, and the footer says commenting needs page.md. Publish a `.md` twin of every HTML page the owner should comment on.
- Republishing reloads the page. Leaving the page (Blocos, another bot, no HTML) disposes the view. The mod never calls the view's `focus` action or any pane/agent focus.
- Not verified on a real window yet: that it renders. Owner's manual test goes in `~/agents/via-assinatura/canvas/ROTEIRO.md`.
