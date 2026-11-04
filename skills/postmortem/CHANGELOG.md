# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-04

### Added
- Procedure: window and anchor, pull events, chain request → read → tools → decision → effect, blameless postmortem, change applied as wiki rule or skill patch.
- `scripts/timeline.py` (uv, PEP 723): compact timeline by turn, or `--json` PROV-like; filters `--card/--turn/--trace`, `--since/--until`; read-only.
- `references/postmortem.md` template.
- `scripts/test_timeline.py`: tests on a throwaway nats-server with fixture events, including `decision.made`.
