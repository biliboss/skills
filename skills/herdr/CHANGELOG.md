# Changelog

All notable changes to herdr are recorded here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-08

### Added

- Scripts over `herdr-app` and `hc` for eight situations: where I am, showing something to the person, delegating to an agent, running a process, another machine, cleaning up, problems, and customizing. Every state change is logged through the `logging` skill (`<script>.start` and `<script>.end`); `-n` dry runs; `close.sh` and `kill.sh` refuse without `--yes`.
- `references/` on surfaces, agents, remote machines, mods and safety, and `scripts/check.sh`.
