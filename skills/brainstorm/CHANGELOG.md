# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-11-06

### Changed

- Learnings from sessions folded in.

## [0.1.0] - 2026-11-06

### Added

- The `brainstorm` skill: a dialogue for an idea still open (one question at a time, 2-3 approaches, design approved in sections) inside a Double Diamond, with Cynefin, the iceberg model, causal loop diagrams and Meadows' leverage points, ending in a design note handed to backbrief.
- `scripts/brainstorm.sh` entry (`uv run` behind it); `scripts/brainstorm.py` (`emit`, `sessions`, `graph`) writing `~/.local/share/brainstorm/events.jsonl` (override `BRAINSTORM_DIR`); `scripts/test_brainstorm.py` (stdlib unittest).
- The Brainstorm domain for the dev-console (`scripts/dev_console_project.py`) with the `CausalLoop` widget: variables as nodes, links as arrows labelled + or -, R / B loops listed.
- `references/tools.md` and `references/prior-art.md`; a README with the credits of every source.
