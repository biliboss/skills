# Herdr Canvas

Requires `herdr-app`, Node 22+ (tests only), Python 3. No packages, no network beyond 127.0.0.1.

```sh
HERDR_APP_HOME=/path/to/herdr/home ./install.sh   # required, no default
```

The installer plans everything first and writes nothing if any anchor is missing. It copies `mod/` to `mods/herdr-canvas/`, adds a `canvas` child to the `panel-body` stack of layouts `main` and `bili-bots`, adds `cmd-alt-c` under `layout:bili-bots` in `keys.json`, applies an idempotent patch to `mods/tabs/main.js` (Canvas added to the enabled panels and a Canvas button after Browser; `--skip-tabs` to omit), backs each edited file up as `*.bak-canvas-<stamp>`, and runs `herdr-app check` (`--no-check` to omit). It never talks to the running Herdr. The mod loads when the panel is first opened or Herdr restarts.

## Page and server

`vendor/canvas.css` (Tailwind + daisyUI, light and dark) is inlined into every page; versions, licenses and rebuild steps in `vendor/README.md`. `skills/herdr-canvas/scripts/canvas serve` serves it on 127.0.0.1 and takes the comments. `mod/pagemode.js` (`ensureServer`) probes the port and starts the server once with `herdr.exec` (`herdr.run` only runs Herdr commands, not processes).

## Native view

With `herdr.nativeView` and kind `web`: URL view, trust `interactive`; server down: `path`, trust `static`, no comments, with a note. Reload on `version` change via `browser.reload` when `canDo`. Never the focus action. Other builds: the Markdown panel.

## Fallback

If the Markdown panel draws a block badly, set `const PLAIN = true;` at the top of `mod/main.js` (or the layout prop `"plain": true`, or the "Texto" button).

## Tests

```sh
node --test test/*.test.js && python3 -m unittest test/test_install.py
python3 -m unittest discover -s ../../skills/herdr-canvas/scripts -p 'test_*.py'
```
