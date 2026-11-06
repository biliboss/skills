# Changelog

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
