# Changelog

All notable changes to the `timer` skill. Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versions: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-05

### Added

- `scripts/timer.sh` (start, pause, resume, add, stop, status, install, quit): the only writer of the state file, atomic, best-effort `mesa.timer.<verb>` event on NATS.
- `app/`: StatusTimer, a display-only menu bar app (AppKit `NSStatusItem`, kqueue on the state directory, Glass sound and notification at zero) and the pure `TimerCore` library with Swift Testing tests.
