# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-11-08

### Changed

- References to the skill `backbrief` now point to `task-backbrief` (renamed); no behavior change.

## [0.1.1] - 2026-11-06

### Changed

- Screens go in as PNGs (2x), four different ideas of the screen, champion by the product's design premise.

## [0.1.0] - 2026-11-06

### Added

- `scripts/tournament.py`: the tournament of 4 (open, round, answer, show, list), its journal and state graph
  (tournament.opened → round.shown ⇄ round.answered → tournament.won); each round drawn on the thread screen.
- `scripts/dev_console_project.py`: the domain `choice` in the dev-console.
