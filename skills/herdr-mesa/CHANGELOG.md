# Changelog

Todas as mudanças da skill `herdr-mesa`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-04

### Added
- A mesa do herdr em fases: um workspace por fase (focus, backlog, working, ready to review, done today), uma aba por item, os panes do item juntos.
- `scripts/fase.sh`: `montar`, `estado`, `mover`, `focar` (cartão à esquerda, agente à direita) e `concluir` (fecha os agentes e deixa o cartão no done today), andando pelo `terminal_id`.
- `scripts/cartao.py`: o cartão minimalista com rich, a partir do `~/.local/state/<tema>.cartao.md` escrito pela sessão do item, na largura do pane.
- `references/cartao.md`: o formato do cartão e o pedido pronto para a sessão.
