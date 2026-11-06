# Changelog

Todas as mudanças do skill `duplo-local-agents`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-04

Junta `herdr-agentes` 0.6.0, `herdr-mesa` 0.1.0 e o `mux.sh` da `prime-agent` numa skill só, independente do multiplexador (herdr, tmux ou nenhum).

### Added
- `scripts/mux.sh` (veio da `prime-agent`), a única porta para um pane; verbos novos `barra` (comando com barra) e `fecha` (recusa se o agente do herdr está working); o `manda` reenvia o Enter se a caixa ficou com "[Pasted text".
- `scripts/herdr/` (SOMENTE HERDR): `fase.sh` (mesa em fases), `backlog.sh`, `bili-trabalho.sh`.
- `fase.sh focar` com o focus montado é uma troca: sempre 4 panes fixos, o da frente vai para working ou backlog, o novo entra embaixo do card (ratio 0.7), a aba é renomeada, grava `focus-set --current X --pick-next` (ou `--next`) e roda `focus-check` se existir. O card e a title-bar não reiniciam.

### Changed
- O `mux.sh` lê os papéis e o multiplexador padrão do `mesa.toml` do `dev/prime-bili` (verbo `papeis`; `<pane>` aceita `human`, `router`, `coordinator`; sem o arquivo, o comportamento de antes). Sem cópia da config na skill.
- **Breaking:** `agente.sh novo` abre um pane à direita (qualquer multiplexador); a aba própria é `--aba` (só herdr) e o `--foco` virou o padrão. Os ids são `HNN`/`TNN`, e o rótulo do pane é `HNN - tema`. `agente.sh` fala com o pane só pelo `mux.sh`.
- A title-bar nasce com ratio 0.1 (o mínimo do herdr), não 0.02.
- O card e a title-bar ficam no `dev/prime-bili` (`just card|title-bar|focus-set|focus-check`); a skill só aponta.

### Removed
- As skills `herdr-agentes` e `herdr-mesa` (sem cópia), o `mesa.sh` (abas doing/review e o `vigiar`) e o `cartao.py`.
