# Surfaces: what the person sees

The window shows spaces, which hold tabs, which hold panes; each pane shows one terminal. The terminals themselves
run in the core (`hc`) and survive the window closing. For exact syntax read `herdr-app --skill`,
`herdr-app commands` (or `scripts/do.sh --list`) and `hc --skill`; this page only holds the rules.

## Addresses

- `$HC_TERMINAL_ID` is a terminal address (`t7`). It is not a pane id. `scripts/whereami.sh` maps it to the pane,
  tab and space; use ids from `scripts/ls.sh` instead of guessing or acting on whatever is focused.
- A terminal started with `hc` is hidden from the window unless it carries the label `herdr.space=<id>`
  (`herdr.tab=<id>` picks its tab; without it a tab is created in that space). Do not add labels just to run a
  background worker. Use the window commands when the person should see something, `hc` when it need not show.

## Creating things

- `space.new` and `tab.new` show immediately. Create them only on request, and always give a name; do not rely on
  default names (`scripts/space-new.sh`, `scripts/tab-new.sh` require `--name`).
- `pane.split` and `terminal.open` land beside the FOCUSED pane. If focus is elsewhere the split appears in the
  wrong place; `scripts/split.sh` refocuses the caller's pane first (and says so in `-n`).
- `terminal.open --folder DIR --place down` starts the split in that folder, also when `--argv` gives a program.
  Without `--folder` it follows the focused terminal's folder.
- A successful launch reply means the terminal was created, not that its program started correctly. If the program
  exits non-zero within two seconds the window shows an error toast. Always `scripts/read.sh` the terminal.
- Mods and layouts can be pane contents too (`mod` argument of `tab.new` and `pane.split`); see `mods.md`.

## Looking and tidying

- `scripts/status.sh` shows layout, focus, zoom, overlays and file or mod errors. A still-working screen is not
  proof that an edit worked; `status` reports a broken save.
- `scripts/shot.sh` saves the window's last frame at full size, even when the window is covered or minimized, with
  no screen-capture permission. Look at the image; do not claim a visual check you did not make.
- `scripts/settle.sh` puts a tab away (out of the lists, still running). It returns when shown or when an agent in
  it needs the person.
- `scripts/zoom.sh` toggles one pane full size; run it again to undo.
- Never experiment with pointer or key automation on the person's real display.
