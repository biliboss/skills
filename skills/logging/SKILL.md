---
name: logging
description: >-
  Use when a script or agent must leave a durable, queryable record of what it did: one JSON line per event in a
  local file, with OpenTelemetry log field names (Timestamp, SeverityText, Body, TraceId, SpanId, Resource,
  Attributes). Triggers "log this", "emit a log record", "registra o evento", "grava no log", "tail the log",
  "consulta o log", "correlate start and end". Bash and jq only, no network, no collector. Not a tracing or
  metrics backend; this is only a local append-only file with rotation.
metadata:
  version: 0.1.0
---
# logging

One record is one line of JSON appended to a file. Any script can call `scripts/emit.sh`.

## Write

```
scripts/emit.sh [--severity LEVEL] <source> <event> [key=value ...]
```

- Appends a record with `Resource {"service.name": <source>}`, `Body` = `<source>.<event>`, `Attributes` from the
  `key=value` pairs (numeric-looking values become JSON numbers; `007` stays a string), `SeverityText` = `INFO` unless
  `--severity` is given (`TRACE DEBUG INFO WARN ERROR FATAL`).
- **Exit 0 means the line is on disk.** Non-zero (message on stderr) means it is not: when the record is a
  precondition for an action, check the exit status and do not proceed on failure.
- Log sizes and ids, never secrets or content you do not own.
- `scripts/emit.sh --trace-id` prints a fresh 32-hex trace id.

## Correlate

`TraceId` comes from `LOGGING_TRACE_ID` (32 hex), else from a valid `TRACEPARENT` (`00-<trace>-<span>-<flags>`),
else a new random one. `SpanId` is always new. An invalid value is ignored with a warning on stderr. To pair a
start and an end: `export LOGGING_TRACE_ID=$(scripts/emit.sh --trace-id)` once, then emit both.

## Read

- `scripts/tail.sh [-n N] [-f]`: last N raw lines (default 20); `-f` follows.
- `scripts/query.sh [--source S] [--event E] [--trace ID] [--since 15m|2h|1d|ISO] [-n N] [--all] [--json]`: TSV
  (time, severity, source, body, trace, attributes) or raw JSON; `--all` includes rotated files.
- `scripts/check.sh`: confirms jq, a writable location and an emit/read-back round trip in a temp file.

## Configuration (environment)

| Variable | Default |
|---|---|
| `LOGGING_FILE` | `$HOME/.local/state/logging/logs.jsonl` (parent folders are created) |
| `LOGGING_MAX_BYTES` | `10485760`; at or above it the file rotates to `.1`, `.1` to `.2`, and so on |
| `LOGGING_KEEP` | `5` rotated files kept |

## Pitfalls

- Writers serialize on a `mkdir` lock (`<file>.lock`); a lock older than 10 s is taken over, so a crash never wedges logging.
- Exit codes in every script: 0 ok, 1 failed, 2 usage; each has `-h`.
- Keep macOS bash 3.2 and BSD tools working: no GNU-only flags.
