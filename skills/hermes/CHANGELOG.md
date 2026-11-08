# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.3.3] - 2026-11-08

### Changed

- References to the skill `backbrief` now point to `task-backbrief` (renamed); no behavior change.

## [0.3.2] - 2026-11-06

### Changed

- Checking the queue: one pass over the Hermes tabs and unsticking an `[unconfirmed]` row.

## [0.3.1] - 2026-11-06

### Changed

- Briefing checklist (`references/briefing.md`), a session per card, orchestrator batching, the owner's words.

## [0.3.0] - 2026-11-06

### Added

- `hermes.sh workspace <slug> --repo DIR [--context|--context-file]`: a Hermes session and a tmux session named slug in the repo, each reused when it exists; the new session's id comes from `--usage-file`, not from the table.

## [0.2.4] - 2026-11-06

### Removed

- Spawn step no longer runs `devc delegated` / `devc done`: a delegation creates no card.

## [0.2.3] - 2026-11-06

### Added

- Spawn step: `devc delegated` right after dispatching, `devc done` when the result arrives (the Kanban card).

## [0.2.2] - 2026-11-06

### Added

- `spawn hacker ... --repo owner/name` runs `kanban.sh wip --repo` first and refuses (exit 6, with the open PRs) at the WIP limit; a failing check only warns.

## [0.2.1] - 2026-11-06

### Changed

- The design profile is `hipster` (was `designer`): hacker, hustler, hipster; the route test covers code -> hacker.

## [0.2.0] - 2026-11-06

### Changed

- Code (a feature, a fix, a PR) routes to the new `hacker` profile, the house's builder.

## [0.1.0] - 2026-11-06

### Added

- `scripts/hermes.sh` (logic in `hermes.py`): `list`, `spawn`, `resume`, `sessions`, `read`, `memory`, `route`, `dm`; a per-profile lock (exit 3), refusal of per-token providers (exit 4), `-z` exit codes passed through, a final JSON line with session id, exit code, duration and usage.
- Routing table (`references/routing.md`) and tests with a fake `hermes` binary.
