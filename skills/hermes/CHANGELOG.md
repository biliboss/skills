# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added

- `scripts/hermes.sh` (logic in `hermes.py`): `list`, `spawn`, `resume`, `sessions`, `read`, `memory`, `route`, `dm`; a per-profile lock (exit 3), refusal of per-token providers (exit 4), `-z` exit codes passed through, a final JSON line with session id, exit code, duration and usage.
- Routing table (`references/routing.md`) and tests with a fake `hermes` binary.
