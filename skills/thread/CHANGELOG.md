# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added

- `thread.sh open|list|close`: a card's topic thread in one call (tmux window + Hermes `/branch` or new session named `<card> · <topic>`), brief inline by argument, stdin or gzip+base64, pasted with bracketed paste.
- Tests with a fake `hermes` and a private tmux server.
