# Changelog

## [0.5.0] - 2026-11-04

### Added
- `bili-trabalho.sh acompanhar|mostrar`: o trabalho passado ao Bili vira um pane na doing com as atividades dele no cartão e o tempo; a resposta leva o pane à review, e Enter retoma a sessão local.

### Changed
- O N das abas conta todos os panes da aba, não só os de agente.

## [0.4.0] - 2026-11-04

### Added
- O fluxo backlog → preparing → doing → review: `backlog.sh puxar <tema>` retoma a sessão ao lado do dono (preparing), e o vigia não mexe na aba do dono.

## [0.3.1] - 2026-11-04

### Fixed
- `mesa.sh` e `backlog.sh` só agem no workspace do herdr de quem os liga: uma sessão de outro workspace era puxada para a aba review.

## [0.3.0] - 2026-11-04

### Added
- `backlog.sh guardar|tirar|arrumar|mostrar|lista`: a aba backlog (N), antes da doing, numa grade igual de até 3 colunas, com um banner por sessão desligada (o que é, onde parou, próximo passo); Enter retoma.
- `mesa.sh organizar|vigiar`: as sessões vão para a aba "doing (N)" enquanto trabalham e para "review (N)" quando param; N é o WIP de cada aba.

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
