# Changelog

All notable changes to logging are recorded here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-08

### Added

- `emit.sh`, `tail.sh`, `query.sh`, `check.sh`: local JSONL log with OpenTelemetry log field names, `TRACEPARENT` and `LOGGING_TRACE_ID` correlation, size rotation, and a `mkdir` lock with stale-lock takeover. Bash and jq only.
