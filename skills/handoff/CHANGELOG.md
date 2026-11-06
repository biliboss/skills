# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-06

### Added

- The guard: Hermes plugin `plugin/handoff-guard` (opt-in per folder with `HANDOFF_AT=<percent>`): injects the handoff order at the threshold, blocks the turn at +15, real context use from `post_api_request`. `scripts/test_guard.py`.

## [0.1.1] - 2026-11-06

### Changed

- "Handoff" means the log line only; branch and `/new` are a separate ask; idle check on the last 3 lines; JSONL optional fields.

## [0.1.0] - 2026-11-06

### Added

- `handoff.sh`: log first (`~/.local/state/bili-sessions.jsonl`), wait for the agent to be idle (600 s cap), fork the
  session offline into a tab right of the agent's (`<tab> antes`), and only with the copy ready send `/new` plus a
  summary to the original. Self handoff runs detached. `handoff.sh log` lists the last sessions with the resume command.
- `test.sh`: 13 checks on a private tmux server with the thread skill's fake hermes.
