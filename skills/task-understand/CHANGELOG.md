# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-05

### Changed

- Renamed to `task-understand`: one command runs the whole workflow; `/tasks` collided with Claude Code's
  built-in command. The domain stays Tasks (`/domain/tasks`, `~/.local/share/tasks`).

## [0.2.0] - 2026-11-05

### Added

- Global append-only journal `~/.local/share/tasks/events.jsonl` (override `TASKS_DIR`), shared by every agent;
  `tasks.py emit` and `tasks.py read` on the command line.
- `scripts/input.py`: the Input contract (frozen value objects) with `check`; the Task Skill widget in the
  dev-console, generated from SKILL.md and input.py.
- The Explain steps in SKILL.md.

### Removed

- The sample journal inside the repo (`scripts/tasks.jsonl`): only real events now.

## [0.1.0] - 2026-11-05

### Added

- Domain design: Task.Explained → Understanding.TaughtBack (teach-back), a hand-editable JSONL journal and the
  dev-console project file.
