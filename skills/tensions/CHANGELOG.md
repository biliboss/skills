# Changelog

## [0.2.0] - 2026-11-05

### Changed
- `EVENTS` is now `{category: {command: event}}`, ordered, and smaller: management `created`/`updated`, observation `recorded`, relationship `linked`/`unlinked`, action `proposed`/`started`/`completed`. Removed: `resolved`, `reopened`, `archived`, `corrected`, `disputed`, `decomposed`, `failed`, and the whole reasoning category. `redefined` became `updated` (old lines still project).

### Added
- `created_at` in the Tension projection: private and immutable, set once by `management.created`.
- `scripts/dev_console_project.py`: Tensions as a dev-console project (the console itself is the `dev-console` skill), with the widgets TensionList and TensionDetail (created), TensionUpdates, ObservationList, LinkedItems, ProposalList.
- `references/tension-model.py`: the Tension model as written in the Linear project.

## [0.1.0] - 2026-11-04

### Added
- `SKILL.md` for agent-native meaningful Tension events.
- `scripts/app_tensions.py` with stdlib-only global append-only JSONL journal and `read` / `emit`.
- `scripts/justfile` as optional shortcuts, without a CLI parser or server.
