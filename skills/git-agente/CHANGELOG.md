# Changelog

Todas as mudanças do skill `git-agente`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-04

### Added
- As sessões de agente do Mac commitam, dão push e abrem PR como `bili-clone[bot]`, com o token de 1 h buscado na hora na VPS (usuário `token-mac`, chave ssh dedicada), nunca em disco.
- `git-credential-bili-mac` (o helper do git, pela conta dona do repo), `gh-bot` (o `gh` como o bot; o `pr create` pede review, o merge é recusado) e `bili-git-agente repo|sessao|conferir`.
- Chaves novas no `casa.env.example`: `CASA_TOKEN_HOST`, `CASA_TOKEN_USUARIO`, `CASA_TOKEN_CHAVE`, `CASA_BOT_NOME`, `CASA_BOT_EMAIL`, `CASA_BOT_REVIEWER`, `CASA_BIN`.
- `tests/git-agente.test.sh`, com ssh e gh falsos.
