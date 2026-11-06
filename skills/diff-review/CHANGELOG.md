# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added

- The `diff-review` skill: an AI code review of a local diff with our own prompt (only introduced problems, a failure scenario each, severity, confidence cut at 80, at most 5, fail-closed JSON), run through pi on the registry of task-understand (`sonnet` default, `glm`).
- `scripts/diff-review.sh` entry; `scripts/review.py` CLI (`run`, `emit`, `findings`, `fix`, `dismiss`); `scripts/test_review.py`; the Review domain for the dev-console.
