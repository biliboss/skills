# Changelog

All notable changes to the `timer` skill. Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versions: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-05

### Changed

- The menu bar looks like the macOS clock: a fixed Nerd Font timer icon (`IosevkaTerm Nerd Font`, SF Symbol `timer` as fallback) and the time in the menu bar font with monospaced digits, label colour (secondary colour when paused, no ⏸ text).
- The label left the bar; it is only the tooltip. `TimerCore` `Display` now tells `running` from `paused` and drops the label truncation.

## [0.1.0] - 2026-11-05

### Added

- `scripts/timer.sh` (start, pause, resume, add, stop, status, install, quit): the only writer of the state file, atomic, best-effort `mesa.timer.<verb>` event on NATS.
- `app/`: StatusTimer, a display-only menu bar app (AppKit `NSStatusItem`, kqueue on the state directory, Glass sound and notification at zero) and the pure `TimerCore` library with Swift Testing tests.
