# Changelog

## [0.5.0] - 2026-11-05

### Added
- A native window the agent drives: `app/` (Swift package, `DevConsole.app`, `com.biliboss.devconsole`) shows the console page in a `WKWebView`, docked at two thirds of the screen on first launch; `scripts/window.sh` (`open`, `reload`, `show`, `hide`, `resize`, `dock`, `eval`, `status`, `wait`, `install`, `quit`) is the only writer of `command.json`, the app the only writer of `state.json` (url, title, visible, size, `last_command_id`, `last_result`, `last_message`). A page talks back through `window.webkit.messageHandlers.devconsole`.
- `ConsoleCore` library with Swift Testing tests: command decode and validation, apply once per id, state encoding, dock and resize frames.

## [0.1.0] - 2026-11-05

### Added
- `scripts/dev-console.py`: one-file FastHTML + MonsterUI console for an event-sourced project, loaded with `--project`; tabs first with vim-style goto, the Model state machine (Human as initial pseudostate, commands as edges) drawn live from the project's `EVENTS`, a contextual sidebar (Widgets, Código, JSON), widgets in a centred popup fed by real events, Observability for every event, all UI state in the query, hot reload.
- `references/project-contract.md`: what a project file declares.
- First project: Tensions (`skills/tensions/scripts/dev_console_project.py`).
