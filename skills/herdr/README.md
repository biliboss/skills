# herdr

Thin, safe scripts over Herdr Desktop: `herdr-app` (the window) and `hc` (its core, where terminals run). The rules
are in [SKILL.md](SKILL.md); the history is in the [CHANGELOG](CHANGELOG.md).

| Situation | Script |
|---|---|
| Where am I | `scripts/whereami.sh`, `ls.sh`, `status.sh` |
| Show something to the person | `space-new.sh`, `tab-new.sh`, `split.sh`, `focus.sh`, `rename.sh`, `zoom.sh`, `settle.sh`, `layout.sh`, `shot.sh` |
| Delegate to an agent | `spawn.sh`, `send.sh`, `keys.sh`, `wait.sh`, `read.sh`, `interrupt.sh`, `label.sh`, `get.sh` |
| Run a process | `run.sh` |
| Another machine | `machines.sh`, `remote-exec.sh`, `remote-file.sh` |
| Clean up | `close.sh`, `kill.sh` |
| Problems | `doctor-status.sh`, `feedback.sh` |
| Anything else in the catalog | `do.sh` |

## Requirements

`bash`, `herdr-app`, `hc`, `jq` and the [logging](../logging/README.md) skill. Set `LOGGING_EMIT` as described in
`example.env` at the repo root.

## Testes

`skills/herdr/scripts/check.sh` runs without changing the window: requirements, logging, `-h`, `bash -n`, dry runs
(`-n`), the `--yes` refusals of `close.sh` and `kill.sh`, and a scan for references the skill must not have.
