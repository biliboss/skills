# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-08

### Added

- Verbo `batch` (`batch.sh`, `batch.mjs`): roda um script `.mjs` no subconjunto da sintaxe de workflows do Claude (`meta`, `args`, `phase`, `agent`, `parallel`, `pipeline`), com limite global de paralelismo (`--max`, `DEVIN_BATCH_MAX`), schema por bloco JSON e estado em `batches/<id>/`.
- Estado `starting` (largada em curso, expira em 60 s).

### Fixed

- `running` enquanto o worker ou o Devin viver (grupo de processos, com hora de início conferida); um `kill` educado vira `failed`, não `lost`; PID reutilizado não segura mais a rodada.
- `run.sh` desfaz pasta, worktree e branch se falhar antes de lançar o worker.
- `clean.sh`: arquivos ignorados contam como trabalho; falha do git recusa em vez de seguir; `--force` sempre termina (repositório sumido, worktree quebrado ou travado); `WORKTREE` e `BRANCH` do `meta.env` precisam bater com a pasta e o id; lida com pasta sem `meta.env`.
- `_worker.sh`: falha do `cd` grava log e `exit` atômico; o pedido vai por `--prompt-file`, não por argv.
- `wait.sh`: `--timeout` inválido e argumentos extras dão erro de uso (2).
- `DEVIN_RUNS_DIR` relativo vira absoluto uma vez.
- `check.sh` e `review.sh` seguem diante de rodada corrompida, worktree sem git ou base inalcançável.

## [0.1.0] - 2026-11-08

### Added

- Delegação ao Devin CLI em background com `run.sh`, `check.sh`, `wait.sh`, `review.sh` e `clean.sh`: um worktree e um branch por tarefa, `swe-2-max` e `accept-edits` por padrão.
