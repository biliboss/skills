# Changelog

Todas as mudanças do skill `sync`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-11-03

### Fixed

- O lint do `.wiki` só roda num wiki do wiki-smith (com `.wiki/wiki.config`); num outro wiki, o `dates.sh` punha frontmatter e o lint cobrava um rodapé que ele não usa.

## [0.1.1] - 2026-11-03

### Changed

- O que outra sessão deixou sujo também entra, num commit separado com o assunto dele: o repo termina limpo. Antes ficava de fora até um "commit all".

## [0.1.0] - 2026-11-03

### Added

- `scripts/sync.sh`: `estado` (ramo, à frente/atrás, sujos, com fetch) e `enviar` (lint do `.wiki` se tocado, commit por caminho, rebase, push, aviso de proteção contornada).
- As regras de quem é cada arquivo sujo, do arquivo compartilhado com outra sessão, do lock do workspace e do lint antes do commit. Manual, sem hook: vira hook se for muito usado.
