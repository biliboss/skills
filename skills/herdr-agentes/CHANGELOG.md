# Changelog

## [0.2.1] - 2026-11-04

### Changed
- Os valores da casa (hosts, usuários, caminhos, contas, ids do Linear) vêm do `casa.env` (`~/.config/biliboss/casa.env`, modelo em `casa.env.example`); a skill veio para o repo público `biliboss/skills`, sem eles no texto.
- O `agente.sh` acha o `pi-claude.sh` pela pasta da própria skill.

## [0.2.0] - 2026-11-03

### Added
- `novo --cwd <pasta>` e `-- <args>` repassados ao harness (testar uma extensão isolada com `-ne -e`).
- Esperar só em segundo plano; teste descartável numa pasta do scratchpad.

## [0.1.0] - 2026-11-03

### Added
- O ciclo de uma sessão local no herdr: `scripts/agente.sh` com `novo` (aba ou foco, Claude Code ou pi, retomar), `manda`, `barra`, `fecha` e `foto`.
- A escolha entre sessão local, Bili pelo Linear e subagente com PR.
