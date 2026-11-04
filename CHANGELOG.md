# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html). Cada skill guarda também o próprio `CHANGELOG.md`.

## [0.4.0] - 2026-11-04

### Added

- `git-agente` 0.1.0: as sessões de agente do Mac (Claude Code, pi, subagentes) commitam, dão push e abrem PR como o bot do GitHub App, com o token de 1 h buscado na hora na VPS por uma chave ssh dedicada (o usuário `token-mac` da VPS só entrega o token), nunca em disco. `git-credential-bili-mac`, `gh-bot` e `bili-git-agente repo|sessao|conferir`. Chaves novas no `casa.env.example`: `CASA_TOKEN_HOST`, `CASA_TOKEN_USUARIO`, `CASA_TOKEN_CHAVE`, `CASA_BOT_NOME`, `CASA_BOT_EMAIL` (e as opcionais `CASA_BOT_REVIEWER`, `CASA_BIN`).
- `delegate-and-review` 0.2.4: o PR do subagente sai pelo `gh-bot`.
- `pi` 0.2.3: o `pi-claude.sh` usa o `git-agente.gitconfig` da pasta da conta, se existir.

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
