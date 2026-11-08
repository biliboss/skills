# Layouts, keys and mods

The installed guide is the authority: read `~/.config/herdr-app/AGENTS.md` (or `$HERDR_APP_HOME/AGENTS.md` when set)
and the generated `.d.ts` files beside it. Do not edit those files; the app rewrites them on start. Overview in
`herdr-app --skill`; discover command shapes with `scripts/do.sh --list`.

- This is the person's configuration. Make only the change asked for and do not touch unrelated mods or settings.
- Mods live in `mods/<name>/` with `main.js` and an optional `mod.json`. They are trusted JavaScript with command and
  network access: read what you are about to install or enable.
- Shipped mods and layouts belong to Herdr. Duplicate first (`mod.clone`, `layout.clone`, via `do.sh`), then edit
  the copy.
- A save reloads. A broken save keeps the old version running and reports an error in `scripts/status.sh`, so a
  still-working screen is not proof the edit worked.
- After every mod change run, in this order: `herdr-app check ~/.config/herdr-app/mods/<name>` (loads the mod once and
  exits non-zero with the exact error), `scripts/status.sh`, then `scripts/shot.sh` and look at the picture. Never
  call a mod done without a passing check, and do not claim a visual check you did not make.
- Use theme colors. Do not keep a mod's `cx` across callbacks; each callback receives its own. Prefer native
  animations over redraw timers. `View.close(cx)` gets one bounded final call; start cleanup there.
- `"focusable": true` in `mod.json` lets `pane.go` move onto a copy of the mod.
- `scripts/layout.sh` switches the shown layout; `app.reset` (via `do.sh`) is the escape hatch that sets the shown
  layout and keys aside. Say so before using it.
