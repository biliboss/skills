# Changelog

## [0.1.0] - 2026-11-05

### Added
- `scripts/dev-console.py`: one-file FastHTML + MonsterUI console for an event-sourced project, loaded with `--project`; tabs first with vim-style goto, the Model state machine (Human as initial pseudostate, commands as edges) drawn live from the project's `EVENTS`, a contextual sidebar (Widgets, Código, JSON), widgets in a centred popup fed by real events, Observability for every event, all UI state in the query, hot reload.
- `references/project-contract.md`: what a project file declares.
- First project: Tensions (`skills/tensions/scripts/dev_console_project.py`).
