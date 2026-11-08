# Herdr Canvas

Requires `herdr-app`, Node 22+ (tests only), Python 3. No packages, no server, no network.

```sh
./install.sh   # HERDR_APP_HOME picks the Herdr config folder (not HERDR_HOME); unset = ~/.config/herdr-app, printed
```

The installer copies `mod/` to `mods/herdr-canvas/`, adds a `canvas` child to the `panel-body` stack of layouts `main` and `bili-bots`, adds `cmd-alt-c` -> `mod.open:herdr-canvas` under `layout:bili-bots` in `keys.json`, backs each edited file up as `*.bak-canvas-<stamp>`, and runs `herdr-app check`. It never talks to the running Herdr. The mod loads when the panel is first opened or Herdr restarts. Idempotent.

The Files/Changes buttons in the tab bar are fixed in the `tabs` mod, so Canvas has no button there: open it with the key, or `canvas open <bot>`.

## Fallback

Not measured on the real app: how `TextView.markdown` draws tables and code, and whether a click on the block body reaches the block. The gutter (number column) is the guaranteed click target. If the body renders badly, set `const PLAIN = true;` at the top of `mod/main.js` (or pass the layout prop `"plain": true`, or click the "Texto" button in the panel header): each block becomes plain text, headings bold.

## Tests

```sh
node --test test/*.test.js && python3 -m unittest test/test_install.py
```
