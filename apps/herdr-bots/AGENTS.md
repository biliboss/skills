# Herdr Bots

The Bots sidebar for Herdr Desktop. `README.md` covers install and session behaviour; this file covers where things are on screen.

## Layout

`install.py` clones the active layout to `~/.config/herdr-app/layouts/bili-bots.json` and edits that copy. A layout is a tree of nodes (`row`, `column`, `stack`, `block`); a `block` shows a mod or the active tab.

```
root  row
├─ sidebar  column, 268px
│  ├─ brand           workspace-chrome           logo, search, collapse
│  ├─ bili-bots       herdr-bots                 this app: main.js, lib/, widgets/
│  ├─ sidebar-lists   column, 0px                mounted, not visible
│  │  ├─ spaces       bili-bot-spaces            clone patched by install.py
│  │  └─ agents       agents
│  └─ sidebar-footer  workspace-chrome {footer}  Settings, Add machine
└─ work  column
   ├─ tabs            tabs                       tabs, +, Files/Changes toggles
   ├─ work-body  row
   │  ├─ main         {tab: active}              terminals; header is mod `pane`
   │  └─ panel  column, 368px
   │     └─ panel-body  stack
   │        ├─ files    files                    file tree
   │        ├─ changes  changes
   │        └─ canvas   herdr-canvas             ../herdr-canvas
   └─ status          workspace-status           machine, agent count, palette hint
```

Only `herdr-bots` and `herdr-canvas` live in this repo. The other mods ship with Herdr, are installed in `~/.config/herdr-app/mods/` and are read-only; to change one, use `mod.clone` and point the layout at the clone.

## Rules

- `install.py` depends on the node ids `sidebar`, `brand` and `spaces`. Unsupported layouts fail on purpose.
- `panel` is `hidden: true` in the file but can be open on screen: clicks (sizes, shown/hidden, active stack child) live in `layouts/.state/` and `tabs` restores the panel per space.
- `install.py` copies `main.js`, `mod.json` and every `.js` in `lib/` and `widgets/` to the mod folder, and fails if either folder is missing. Files elsewhere are not copied.
- Icons are referenced from the Herdr home (`mods/<name>/x.svg`), so `widgets/StatusMark.js` depends on `workspace-chrome` for `spinner.svg`.
- Run `herdr-app check <mod folder>` after every mod change. Herdr's full reference is `~/.config/herdr-app/AGENTS.md`, sections Layouts and Mods.

## Widgets

The bots panel is built from small widgets in `widgets/`. `main.js` holds state and wiring, `lib/registry.js` reads the registry and opens bots, `lib/layout.js` holds the layout code.

```
BotsPanel                         bots.panel
├─ PanelTitle                     bots.title
├─ BotList                        bots.list
│  └─ BotRow                      bots.row:<id>
│     ├─ BotIcon
│     ├─ BotName
│     ├─ StatusMark
│     └─ ShortcutHint
└─ ErrorLine                      bots.error
```

- File and exported function share one name. Widgets that need an id use the `bots.<name>` form shown above.
- A widget is a pure `(props, t) => element`. It never imports `"herdr"` and holds no state.
- State and Herdr calls stay in `main.js` and `lib/`.
- A new widget needs only a file in `widgets/`; the installer copies the folder.
