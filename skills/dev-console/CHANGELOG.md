# Changelog

## [0.31.0] - 2026-11-06

### Changed

- The Home is a SQLite table: `home` (starts with only the logo widget; position, span, height, `parent_id` composition) and a live `widgets` catalogue, in `~/.local/share/dev-console/dev-console.sqlite` (`DEV_CONSOLE_DB`, WAL). The page renders from `home` and follows edits made outside the console (watchfiles on the db and its -wal). The logo is now a real widget (`Logo`) of the dev-console's project; `devc home show` gains `--position` and `--parent`; `rm` of a parent removes its children. The old JSONL is migrated once and kept as archive. Tests: `test_console_home.py`.

## [0.30.6] - 2026-11-06

## [0.30.7] - 2026-11-06

### Changed

- New empty Home with the logo (old home kept unrouted as `_old_home`); Native widgets on the status line (marks drawn in code, data from a console route, event-stream items), Claude account usage, widget check by curl, interactive report state in the URL hash, start from a stable folder.

### Changed

- Declares the dependency on the `tmux` skill for agent state: `agent-state.sh` marks the window (`@agent`, `@done`); where a view shows an agent's state it reads those first and scrapes the pane only as fallback (the Quadro's agent line, in `kanban`, does).

## [0.30.5] - 2026-11-06

### Changed

- A project may rename a module and keep the old name: `MODULE_ALIASES = {"Quadro": "Kanban"}` makes `?tab=Quadro` open the renamed module (`D.module_aliases`). Test: `test_console_palette.py`.

## [0.30.4] - 2026-11-06

### Changed

- "Edit right here" means in the session; anything local he must see (landing, interview, HTML report) goes through `devc browse`.

## [0.30.3] - 2026-11-06

### Fixed

- The home module (`CONSOLE_HOME`, the Kanban's Quadro) is in ⌘P on every page, first, not only on `/domain/kanban`: `_modules` and `/api/palette` add it through `_home_module()` (no duplicate on its own domain). `/api/palette` lists Browser too, like the web list. Test: `test_console_palette.py`.

## [0.30.2] - 2026-11-06

### Changed

- `devc browse <url>` is listed in the devc block: the interview skill (1.1.0) opens its queue page there when the console is up, and nothing when the window already shows it.

## [0.30.1] - 2026-11-06

### Changed

- Learnings from sessions folded in.

## 0.30.0

- Hot reload also reads what a project imports: the watcher follows the folders on sys.path, the loaded modules' folders and the project's `WATCH` list (kanban: cost-track's costs.py), and a re-import drops the project folder's cached modules first (`console_reload.py`). The main console no longer serves stale kanban code until a restart.
- `/costs/stream` (SSE): watchfiles follows the Costs journal and running.json (`COSTS_DIR`) and the money bar re-reads the clock and fires `devconsole-money` at once, so a tmux focus switch shows on screen in under 1 s. The 10 s refresh stays as a fallback.

## 0.29.2

- The window no longer drives the cost clock (focus, hidden, idle, domain switch): `time/start|enter|beat|stop` only read, behind `DEVC_CLOCK_DRIVER=1` (default off). The clock is written by cost-track's `costs.sh tmux-focus`; the bar still shows it.

## 0.29.1

- Removed `devc delegated` and `devc done` (0.29.0, #129): one card per piece of work the owner names; subagents never create cards. `devc board` stays.

## 0.29.0

- devc gains the Kanban: `devc delegated "<goal>" --domain D [--parent CARD] [--by bili-local]` creates a card in
  Downstream the moment a subagent is dispatched (title trimmed to 80 characters, prefixed by the parent's title;
  idempotent per title and domain while the card is open), `devc done <card> [--note]` moves it to Feito, and
  `devc board [args]` is the passthrough to `kanban.sh`. All through `kanban.sh`; devc never writes the journal.

## 0.28.0

- The graph moves like a map: two fingers on the trackpad (or a mouse wheel) pan it, a pinch or ⌘ + scroll zooms around
  the pointer (Chrome's wheel + ctrlKey and WebKit's gesture events, so DevConsole.app pinches too); the page never
  scrolls under it.
- No graph label renders under 14 px: the zoom has a floor (14 / the smallest label font), so fit, the home view and a
  pinch stop there and a big domain opens larger than the window, read by panning. The dashed edges' commands go from
  12 to 14 and the lane legend to 14 px. Lanes, labels, the side panel and the home stay as in 0.27.0.

## 0.27.0

- Restores the domain page and the home to 0.24.0 (before the folded lanes of 0.25.0 and the focus home of 0.26.0): the owner lost the side panel and the event texts. devc stays.

## [0.26.0] - 2026-11-06

### Added

- **The focus home (`g h`)**: the focus is one pointer, a stack in `~/.local/share/dev-console/focus/events.jsonl`
  (`focus.set {text, target, card, by}`, `focus.back`), written only by `scripts/focus.sh set|back|show` and moved only by
  the owner's conversation with the Bili (`by` gabriel or bili; anything else refused). The Kanban board is the default
  focus. `/` (and `g h` on every page) opens `/home`: the Kanban card in focus (the top of Downstream, else of Upstream; title, domain, time in its stage, the Kanban's money for it) with the focus embedded (a domain's graph, a widget, a console page or the recorder's last shot) and the last 5
  focuses; with the Kanban as focus or no card in focus, the board. `GET /agent/focus` (`devc focus`). Code in
  `console_focus.py`, tests in `test_console_focus.py`.
- DevConsole.app opens the home at launch (`launchURL` in `ConsoleCore`), not the last URL it saved.

## [0.25.0] - 2026-11-06

### Added

- **Focus + context on a big domain's branch layout** (more than 15 events; Furnas 1986). It opens with one lane drawn
  whole (the journal's latest event's lane, else the `HOME` event's, else the first) and the others folded to one line:
  dots, no labels, nothing dashed, and the lane's name and count as a frozen row header at the window's left edge. A click
  on a folded lane, or its number key (1-9), opens it and folds the previous; `0` opens all; the legend is the same
  switcher; `?lane=<cat>|all` keeps it. A column with no open-lane station narrows to 44 px, a stage band never below its
  header, so the open lane stays readable; the fit fits the open lane, not everything. Via: the session lane at 0.87, the
  others one line each; Zap: the account lane (its `HOME`) and ten named rows, where every lane born right of the window
  had no visible name before.
- **Labels never below 16 px at 1140×1074**: the branch zoom floor is 0.81 (every branch label 20 px, the dashed edges'
  too, were 17), and `min-zoomed-font-size` 16 hides a label a hand zoom-out would shrink below that.

### Fixed

- **`render_screens` shows the product's screen with its own frame only, scaled to fit.** A step may say where the
  product draws its device frame in its page (`frame: [x, y, w, h]` inside `viewport: [w, h]`, its `radius`): only that
  box shows, so Storybook's padding and the catalogue's margin no longer read as a second, white frame. The box scales
  to the stage (never above `scale`, now 1), so a 406 x 860 phone or an 808-wide board fits the popup at any window size;
  the fixed 390 x 844 iframe cut every Via story on the right and the bottom.
- The ← → were `<button>`s that Pico paints as blue squares (the arrow sank to the bottom): now grey text controls,
  focusable, dimmed at the ends, and the ← → keys step too. One step shows no arrows.
- The popup no longer cuts the screen: a widget whose root says `data-pop="stage"` gets a popup of `min(1180px, 94vw)`
  by `min(1000px, 92vh)` and its stage takes the height left, with nothing to scroll.
- A `data-real-only` widget opened with `?mode=sim` kept the SIMULADO stripes and banner: the mode is cleared and
  repainted. Real screens are `data-real-only` (nothing to simulate).
- **Branch layout, readable at his window**: station labels 20 px (were 14: about 8 px rendered on a 1440 x 900 window,
  12 now; 15 at 1140 x 1074), columns 210 apart to hold them, the entity named once at each lane's first station.
- **Branch layout, no dashed line across the map**: a jump into another lane, or a loop back inside a lane over more
  than two columns, is drawn as its end only (partial edge drawing), a short dashed stub labelled `command ← Source`. On
  the Via `open_by_client` crossed all five lanes and `view_index` ran 1900 px along the session line.
- **Branch layout, the broker's exits**: the grey spine of a lane that hangs from the Human ran its 45° leg through
  Broker.SignedUp, on top of the yellow line; it now goes down the Human's column and along its own row.
- A spur that ends at its station carries the label on its right (stacked spurs pushed labels 113 px away); a station
  nothing in its lane leads into continues its own row (its rail cut across a fork); labels knock out the line under them
  in their stage band's tone.

### Changed

- The dots are a list of the steps beside the screen: number, name, the event the screen leads to, and the current
  step's note; a click, Enter or Space on a row opens it.

## [0.24.0] - 2026-11-06

### Added

- **`devc`**, the app's own CLI (`scripts/devc` + `devc.py`, PEP 723, stdlib): `domains`, `show <slug>` (lanes, transitions, events as a small git-log graph), `events <slug> [--tail] [-n N]`, `focus`, `open`, `shot`, `now`, `history`, `eval`, `start`, `stop`, `list`, `check`, `install`; `--port` and `--json`. The older scripts stay and `devc` calls them. `test_devc.py` uses a fake console.
- `.sesskey` in `.gitignore`.

## [0.23.0] - 2026-11-06

### Added

- **`/` is the console's home**: the module a domain names with `CONSOLE_HOME` (the Kanban's Quadro, skill `kanban`) when that domain's journal has an entity; else the first domain, as before. The Playground's and Agents' ⌘P "Domain" and `/api/palette` without a domain now link the first domain by its URL (what `/` used to open).
- **A module can be a project widget** (`MODULE_WIDGETS` in the project contract): full width, its leading title hidden, goto key the first free letter of its name, beside the same contextual sidebar.
- **An entity's sidebar** (`ENTITY_PARTS`): a click, Enter or Space on a `[data-entity]` element of a widget module opens the console's sidebar with the project's widgets for that entity as expandable parts, then its JSON; `?ent=` keeps it open, Esc closes it; the selection survives the widget's redraws. One `SIDE_HTML` and one `partHtml` for the event sidebar and this one.
- The money bar dispatches `devconsole-money` on `document` after each start, stop or enter, so a widget that draws money redraws at once.
- `console.sh url ... --ent <id>`.

### Fixed

- A domain page no longer asks for `/favicon.ico` (an empty icon link, like the Agents page): `check.sh` on a domain page reported that 404 as an error.

## [0.22.1] - 2026-11-06

### Changed

- **The branch layout (rails) is the default domain view.** A project's explicit `LAYOUT` still wins. The rays/metro view stays behind `L` only; the corner button is gone and the layout name shows as a brief toast when `L` is pressed.

## [0.22.0] - 2026-11-06

### Added

- **Agent API and flight recorder.** DevConsole.app writes one JSON line per navigation to `~/.local/state/dev-console/recorder/events.jsonl` (`DEV_CONSOLE_RECORDER_DIR`) with a PNG from `WKWebView.takeSnapshot`; the last 20 lines and PNGs stay. Page JS errors ride on the line. Read-only `GET /agent/now`, `/agent/history?n=`, `/agent/shot` (app, else headless), and `scripts/agent.sh now|history|shot|open|eval|status`. `window.sh shot` and `window.sh running`. `ConsoleCore/Recorder.swift` with tests; `test_console_recorder.py`.

## [0.21.1] - 2026-11-06

### Fixed

- ⌘K/⌘P in DevConsole.app open the native palette: the app reads them before the web view, which swallowed them (only the Go menu worked). Test: `ShortcutTests`.
- Rule for testing real keys without typing into the owner's front app.

## [0.21.0] - 2026-11-06

### Added

- **Native status line** in DevConsole.app (chrome drawn by the window, content kept by the page): ▶/⏸, cost center, R$ today with budget, domain and module, live. The page pushes `postMessage({type:"status"})` and hides its own bar only inside the app; `window.devconsoleToggle()`; read-only `GET /api/status?domain=<slug>`; 8 s fallback refresh. `ConsoleCore/StatusLine.swift` (`formatBRL`, `StatusInfo.decode`) with tests.

## [0.20.0] - 2026-11-06

### Added

- Native chrome: DevConsole.app has its own command palette (`PaletteController`), a floating vibrancy panel over the window; ⌘K lists domains, ⌘P modules, Enter loads the URL in the web view (the page's first gesture still posts `time/enter`). Fuzzy ranking (`fuzzyMatch`, `fuzzyRank`) and the palette model live in `ConsoleCore`, with tests.
- `GET /api/palette[?domain=<slug>]`, read only: `{domains:[{slug,name}], modules:[{id,title,url}]}`.

### Changed

- Inside the app the page's own ⌘K/⌘P overlay is off (a click on the status line asks the native palette); a plain browser keeps it unchanged.

## [0.19.0] - 2026-11-06

### Added

- `scripts/check.sh <url>` (logic in `check.py`, uv PEP 723): a headless check of a console page with the installed Chrome (playwright `channel="chrome"`), for harnesses without a browser tool; JSON with status, title, console and page errors, an `--eval` value and a screenshot; exit 1 on any error.

## [0.18.0] - 2026-11-06

### Changed

- Agents: the toolbar is grey console text in one line (no `role="button"`, which MonsterUI paints blue; Enter and Space work), the same in both views (the Prompts-only chips are dimmed in the Log); tool rows say what the call is about (`Bash: <command>`, `Edit: <dir/file>`); sessions show their `/rename` name; no favicon 404. Fixed: the console loads `console_agents` and `console_playground` by path before any project, so a test console no longer runs another checkout's copy.

## [0.17.0] - 2026-11-06

### Added
- The **Agents** module, `/agents` (⌘P lists it): the prompts the owner typed to Claude Code (allow-list: `origin.kind == "human"` with `promptSource` `typed` or `queued` (marked `queued`); peer = `cross`, task-notification = `notification`, anything unknown = `other`) and the agents' session logs, in real time. Prompts and Log views, filter by session, chips, pause, click to expand. Routes `/agents/api/prompts|log|entry` and SSE `/agents/events` (`Last-Event-ID`, `retry`, keep-alive). `DEV_CONSOLE_AGENTS_DIRS` sets the roots (default `~/.claude/projects`, deduplicated by realpath).
- Following by events: one `watchfiles` watcher thread (about 100 ms from the write to the SSE message), a 5 s rescan as the safety net, and a ~1 s polling fallback with one warning line if `watchfiles` cannot be imported. `watchfiles` is now a declared dependency of `dev-console.py`.
- Prompts typed mid-turn: they are logged as `attachment` / `queued_command` lines, now read (human = queued `prompt`, peer = `cross`, task-notification = `notification`, other = `other`), and de-duplicated against the later `user` line (same session, kind and text head within ~2 minutes; the earliest stays).
- Security: `TrustedHostMiddleware` on the whole app (400 for any `Host` but `127.0.0.1`, `localhost` and `DEV_CONSOLE_ALLOWED_HOSTS`; DNS rebinding); no CORS.
- SSE without polling: one `asyncio.Queue` per client fed by the watcher thread; the watcher thread stops on shutdown. `DEV_CONSOLE_AGENTS_BACKFILL_FILES` sets how many files the backfill reads (default 150).
- `scripts/console_agents.py` (source, normalizer, hub, SSE, page script; pi and Hermes plug in as another source class) and `scripts/test_console_agents.py` (synthetic lines only). A `README.md` for humans.

## [0.16.1] - 2026-11-06

### Changed

- Naming guidance cites `backbrief` (renamed from task-understand).

## [0.16.0] - 2026-11-06

### Added
- The Playground is served by the console itself: the design-playground's canvas web (`scripts/playground/`: `canvas.js`, `widgets.js`, `paleta.js`, `app.css`, plus `eventos.js`) same-origin, no iframe, no chat. ⌘K and ⌘P now work with the canvas focused (the key handlers listen in the capture phase).
- `scripts/console_playground.py`: the Python port of the design-playground's server (canvas mirror, component validation and wrapper-folder reader, operations on the open page, SSE) and its routes `/playground/api/{canvas,canvas/diff,canvas/resposta,componentes,eventos}`, with the TS's JSON.
- Data in `~/.local/state/dev-console/playground/` (`DEV_CONSOLE_PLAYGROUND_DIR`), same format as before; `console.sh playground import [<dados dir>] [--force]` copies it from the design-playground once.

### Removed
- The iframe, `DEV_CONSOLE_PLAYGROUND_URL`, `GET /playground/up` and the "design-playground não responde" page.

## [0.15.0] - 2026-11-06

### Added
- `scripts/console.sh`, the agent's one door: `list`, `start` (a herdr tab `dev-console:<port>` by default, `--no-tab` for the foreground, `--dry-run`, next free port when none is given), `stop`, `claim`, `domains [port]` / `domains add|remove`, `state`, `url`, `actions`.
- One append-only journal of instance owners, `~/.local/state/dev-console/instances.jsonl` (`instance.started`, `instance.claimed`, `instance.stopped`); `list` projects the owner from it.
- Read-only JSON routes: `GET /api/domains`, `GET /api/domains/<slug>/actions`, `GET /domain/<slug>/state.json[?task=<id>]`. The page and `state.json` share `_page_data`.
- `window.sh --owner <name>` (a state directory per owner) and `window.sh --owner <name> launch [url]` (a second native window); the app saves its frame per state directory.

### Changed
- `list` shows every domain of an instance, the registry's too (they were hidden).
- `instances.sh` and `second.sh` are thin wrappers over `console.sh`; the per-port owner files are gone (the journal replaces them).

## [0.14.0] - 2026-11-06

### Added
- `scripts/instances.sh`: `list` (every running instance: port, owner, where its code comes from, domains, live reload, start time and pid), `start [port] [--from 5057] --owner <name>` (the second instance's logic, now requiring an owner, which it records in `~/.local/state/dev-console/instances/<port>.json`) and `stop <port> [--force]` (kills the process tree; 5057 needs `--force`). Without an owner file, `list` shows the herdr pane, the tmux pane or the tty.

### Changed
- `scripts/second.sh` is a thin wrapper that runs `instances.sh start`; it now needs `--owner`.

## [0.13.0] - 2026-11-06

### Added
- `--no-live` (and `DEV_CONSOLE_LIVE=0`): the server does not reload open pages on a save.
- `scripts/second.sh [port]`: a second independent instance on its own port (default 5058), without live reload, one per agent; it copies the `--project` flags of the instance on `--from` (default 5057), so both show the same domains.

## [0.11.0] - 2026-11-06

### Added
- ⌘P (Ctrl+P in a browser) opens the **module switcher** on every page: the ⌘K overlay (same look and keys, fzf-style typing) over `D.modules`, one list of `{name, href}` built by one server function (`_modules`): Domain and the project's `TABS` (`href: null`, shown in place), then Playground (`/playground`, navigates). The current module reads "· atual". ⌘K lists **domains only** (the Playground row is gone from it). The page exposes `window.devconsoleModules()` (and `devconsoleDomains()`); the key never opens the browser's print panel.
- Native app: a "Go" menu with "Domínios" (⌘K) and "Módulos" (⌘P) that evaluate those functions in the page, so AppKit's ⌘P (Print) never opens a panel (`PageOverlay` in `ConsoleCore`, tested).
- The Playground page has the same bottom status line (`_status_bar`) and ⌘P; its name in the status line is "Playground". The switcher script stays one copy (`SWITCHER_JS`, cut from the page's JS).

### Changed
- The tab bar is gone. One thin status line (28 px) at the bottom replaces the toolbar: `<domain>` (click = ⌘K), `· <module>` (click = ⌘P), the money bar (unchanged; its popover opens upward and the over-budget note rides on the first row), and a faint `⌘K domínio · ⌘P módulo`. The graph takes the full height. `?embed=toolbar` and `?embed=money` render the status line and the money piece alone.

### Fixed
- Loading `/playground` no longer ends a stretch running elsewhere: only `POST time/enter` on a person's first trusted gesture does, there as on a domain page (`time_enter` answers for the Playground too).
- `?embed=money` showed an empty line: it now shows the bar (read-only state; the ▶ works on click). An embed still never enters, beats or stops the clock on its own, except for a stretch its own click started.

## [0.10.0] - 2026-11-06

### Added
- The Playground mode, `/playground`: the console's bar plus the design-playground's canvas in an iframe (composed, not copied; its chat comes with it, its web has no canvas-only mode). `DEV_CONSOLE_PLAYGROUND_URL` (default `http://127.0.0.1:5317`); when it does not answer the page says so in one line with the command that starts it and opens the canvas by itself when it does (`GET /playground/up`).
- The Playground's money bar: `PLAYGROUND_COST_CENTER` (env `DEV_CONSOLE_PLAYGROUND_COST_CENTER`, default `biliboss-skills`), served by the existing `/domain/playground/time*` routes.
- `D.modules` (`{name, href}`) on every page; ⌘K lists each module but Domain as a fixed last row ("Playground"). The Domain Switcher script and overlay are now shared by both pages (`SWITCHER_JS`, `_switcher()`).

## [0.9.0] - 2026-11-06

### Added
- `LAYOUT = "branch"` (project file): the graph as a git graph read left to right. The Human is the root at the top left; each category of `EVENTS` is a horizontal lane, top to bottom in `EVENTS` order; a line follows `TRANSITIONS` (trunk = the longest path, a fork is a 45° spur inside its lane, a back edge a dashed arrow). A lane starts one column right of the station whose transition leads into it, joined by a 45° connector (a vertical gutter between two 45° legs when the lane is far below); a lane nothing leads into hangs from the Human on a grey spine; an edge into another lane later on is a merge (thin, grey, dashed, one bend, with its command). Labels are horizontal, below or above the station, and never overlap.
- `STAGES = {"cat.event": "stage"}`, `STAGE_ORDER = [...]` and `STAGE_LABELS = {...}` (project file, optional): columns are funnel stages, each a band with a faint header at the top; a station sits in its stage's band, ordered by the path; an edge back to an earlier stage is drawn as a loop. Without `STAGES`, columns are the step count from the Human. The three travel in the model payload like `layout`.
- `L` (focus not in an input) and a small text button in the graph's top-right corner (`ramos` / `raios`) toggle the drawing between branch and metro on any domain, remembered per domain in localStorage; the project's `LAYOUT`, else metro, stays the default.
- The branch drawing opens with the Human at the top left with a margin and the zoom fitting the height; "Centralizar Human" puts it back there.
- `cy.scratch('branch')`: the lanes' y bands and the stages' x bands, for headless checks.

### Changed
- A redraw destroys the previous cytoscape instance and disconnects its resize observer (the toggle redraws).
- The metro's station labels also avoid dashed edges' routes in the branch drawing, and may take the other side when the first is crowded (branch only).

## [0.8.0] - 2026-11-06

### Changed
- Metro is every domain's default, drawn as the sun's rays (see SKILL.md); `0.7.1`: a metro line follows `TRANSITIONS`, a fork is a 45° branch, a back edge stays dashed.

## [0.7.0] - 2026-11-05

### Added
- `LAYOUT = "metro"` (project file): the graph of a big domain reads like a Tokyo Metro map, deterministic (preset positions computed in `drawGraph`, no force layout), octilinear after Nöllenburg & Wolff 2011. Each category of `EVENTS` is a line in its own colour leaving the Human along its clock hour (the first at 12 o'clock, the others clockwise) snapped to one of 8 directions; categories that snap to the same direction are fanned, parallel, one track apart. Stations are small dots, evenly spaced in `EVENTS` order, the first one a ring from the Human. Edges between neighbouring stations are the line itself (6 px, category colour, no arrow, no label); edges that leave a line (`TRANSITIONS`) are 2 px, grey, dashed, octilinear with at most one bend, with their command label. Labels are horizontal, on a fixed side of the line, wrapped at PascalCase words and pushed apart until no label meets another label, a station or a line. The Human stays the biggest node and the centre; filled / outlined still means a record / none yet.
- `"clock"` keeps working as before.

## [0.6.0] - 2026-11-05

### Added
- The money bar in the toolbar of every domain with a cost center: the center, what it spent today in R$ (ticking every second), `de R$ <budget>` with a thin progress line (red over budget, `hoje a <cliente> pagou R$ X/h`) for a client, `<nome> · R$ X hoje` for an investment, the rate (R$/min, click cycles min, hora, dia; kept in localStorage) and ▶ / ⏸. A click on the center name opens a popover with today per center and the total.
- `POST /domain/<slug>/time/start` and `/time/stop` (`ended_by`) emit `time_entry.started` and `time_entry.stopped` through cost-track's `costs.py` (the only writer of the Costs journal; if the file is missing there is no bar); `GET /domain/<slug>/time` and `POST .../time/beat` support the bar. The running stretch lives in `running.json` in the costs folder, so a hot reload keeps it; a page silent for 45 s is closed (`close`).
- The clock stops on Pause, on switching domain, on the page hidden (`visibilitychange`) and after 5 minutes idle on the Mac; never on window blur. The native app calls `window.devconsoleIdle(seconds)` every 5 s with the Mac's idle time (`systemIdleSeconds()`, any input event type); a browser falls back to its own input idle. Coming back does not restart the clock.
- `COST_CENTER` in a project file (see references/project-contract.md).

## [0.5.0] - 2026-11-05

### Added
- A native window the agent drives: `app/` (Swift package, `DevConsole.app`, `com.biliboss.devconsole`) shows the console page in a `WKWebView`, docked at two thirds of the screen on first launch; `scripts/window.sh` (`open`, `reload`, `show`, `hide`, `resize`, `dock`, `eval`, `status`, `wait`, `install`, `quit`) is the only writer of `command.json`, the app the only writer of `state.json` (url, title, visible, size, `last_command_id`, `last_result`, `last_message`). A page talks back through `window.webkit.messageHandlers.devconsole`.
- `ConsoleCore` library with Swift Testing tests: command decode and validation, apply once per id, state encoding, dock and resize frames.

## [0.1.0] - 2026-11-05

### Added
- `scripts/dev-console.py`: one-file FastHTML + MonsterUI console for an event-sourced project, loaded with `--project`; tabs first with vim-style goto, the Model state machine (Human as initial pseudostate, commands as edges) drawn live from the project's `EVENTS`, a contextual sidebar (Widgets, Código, JSON), widgets in a centred popup fed by real events, Observability for every event, all UI state in the query, hot reload.
- `references/project-contract.md`: what a project file declares.
- First project: Tensions (`skills/tensions/scripts/dev_console_project.py`).
