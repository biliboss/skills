# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added

- `scripts/tournament.py`: the tournament of 4 (open, round, answer, show, list), its journal and state graph
  (tournament.opened → round.shown ⇄ round.answered → tournament.won); each round drawn on the thread screen.
- `scripts/dev_console_project.py`: the domain `choice` in the dev-console.
