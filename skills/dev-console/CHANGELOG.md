# Changelog

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
