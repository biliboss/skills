# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-11-05

### Fixed

- The default executor follows the claude-code skill: `--max-turns 30`, allowed tools only, its own git worktree and
  JSON output (cost, turns, session id recorded in `task.executed`); before, it edited the shared checkout with no cap.
- `test_flow.py` runs with `uv run python scripts/test_flow.py`.

## [0.5.0] - 2026-11-05

### Added

- `tasks.py use-learnings` (real `learning.used`), `feedback` (`feedback.given` + downscore), `options` (`option.generated` x3),
  `choose` (`option.chosen` + score) and `styles` (scores, default = highest).
- Three fixed, versioned styles (`STYLES`); the projector keeps `options` and `style`; `scripts/test_flow.py`.
- SKILL.md: Styles section and steps 6 to 9 (learnings, feedback, options, choice).

## [0.4.0] - 2026-11-05

### Added

- `tasks.py execute --task <id>`: runs the configured executor on a confirmed task and records `task.executed`;
  default is Claude Code print mode on the mukutu account with Sonnet, configurable in `~/.config/tasks/config.json`.
- Draft of the whole process in the dev-console graph: Learning (recorded, used), Understanding.Confirmed by the
  Human, Feedback.Given, three styled Options (generated, chosen), Style.Scored by score or downscore, Task.Executed.
- Steps 5 to 7 in SKILL.md: adjustments become learnings, learnings are used before repeating back, execute after
  the confirmation.

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
