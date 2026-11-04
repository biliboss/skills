# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html). Cada skill guarda também o próprio `CHANGELOG.md`.

## [0.4.0] - 2026-11-04

### Added

- `envless` 0.1.0: o segredo entra no comando pelo `envless exec`, nunca na conversa; `list` sem valores, `set` pelo stdin, `get` só com `--confirm`; quando usar o CLI e quando o `envless mcp`. As armadilhas: o envless não sobe de pasta e um `--env` inexistente volta vazio, os dois com exit 0.
- `disky` 0.1.0: o diagnóstico de disco com o disky (`scan`, `dirs`/`top`/`ext`/`query` com `--physical`, `cleanup` em dry-run) e a tabela (caminho, tamanho, o que é, se se regenera) que o dono aprova antes de qualquer apagamento; o espaço liberado medido pelo `df`, porque no APFS o tamanho apagado não é o liberado.
- `herdr-mesa` 0.1.0: a mesa do herdr em fases, um workspace por fase (focus, backlog, working, ready to review, done today), uma aba por item e o cartão de cada item no focus (`scripts/fase.sh`, `scripts/cartao.py`).

### Changed

- `herdr-agentes` 0.6.0: o fluxo da mesa (o `mesa.sh` e as abas doing/review) saiu; a seção aponta para a `herdr-mesa`.

## [0.3.0] - 2026-11-04

### Added

- `design` 0.1.0: telas no design-playground com os widgets reais do produto. O wrapper sai do código do produto (`scripts/wrapper.sh build|conferir|pastas|foto`) e o agente vira o motor do MCP (`scripts/motor.sh claude|pi|http`). O que é de cada produto (a referência, a receita, os wrappers e os rascunhos) mora fora do repo, em `DESIGN_PRODUTOS`. Chaves novas no `casa.env.example`: `DP_DIR`, `DP_URL`, `DP_URL_REMOTA`, `DP_TOKEN`, `DESIGN_PRODUTOS` e `PRODUTO_<P>_REPO`/`_REMOTO`.

## [0.1.2] - 2026-11-03

### Changed

- `skill-smith`: as ações de um skill são scripts `.sh`, não um servidor MCP.

## [0.1.1] - 2026-11-03

### Changed

- `sync` 0.1.1: o trabalho de outra sessão também é commitado, em commit separado.

## [0.1.0] - 2026-11-03

### Added

- O plugin `biliboss-skills` e o marketplace `biliboss`, no molde do mattpocock/skills.
- `wiki-smith` (de biliboss/wiki-smith, 0.1.2), `skill-smith` (de biliboss/skill-smith), `lp-draft`, `sync` (do biliboss) e o novo `setup-biliboss`.
