# Changelog

## [0.1.0] - 2026-11-06

### Added

- The `retro` skill: the on-demand `/retro` procedure (find lessons, filter, shape, ask, apply in one PR, track recurrence), following `references/prior-art.md`.
- `scripts/retro.py` CLI (`uv run --script`, stdlib): `emit`, `lessons`, `rejected-rules` and `scan` of a Claude Code session JSONL (marker, correction, tool_error, praise); the module API the dev-console imports is unchanged.
- `scripts/test_retro.py` (stdlib unittest).
