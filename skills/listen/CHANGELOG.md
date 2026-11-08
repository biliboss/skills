# Changelog

## [0.1.0] - 2026-11-08

### Added

- `listen <bot> [--as <ouvinte>] [--events stop,notification] [--off]`: registra ou remove, no settings do bot ouvido,
  os hooks que avisam o ouvinte via `ag-notify`; merge sem apagar outros hooks, idempotente, `needs_reload` quando o
  alvo está vivo.
