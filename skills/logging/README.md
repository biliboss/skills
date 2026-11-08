# logging

A local, append-only JSONL log with OpenTelemetry log field names, written by one small script. The rules are in
[SKILL.md](SKILL.md); the history is in the [CHANGELOG](CHANGELOG.md).

| Command | Example |
|---|---|
| Write | `scripts/emit.sh myjob started count=3` |
| Last lines | `scripts/tail.sh -n 5` |
| Filter | `scripts/query.sh --source myjob --since 1h` |
| Self-test | `scripts/check.sh` |
