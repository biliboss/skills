# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-09

### Added

- Pasta do agente como entrada: todas as sessões em ordem de tempo; sem argumento, usa a pasta atual.
- `--last N`: só as últimas N falas do dono.

### Changed

- O agregado passa a ser `AgentMemory`, com `scope` no lugar de `sessionId`.

## [0.1.0] - 2026-11-09

### Added

- `scripts/memory.ts`: extração incremental de fatos por janelas com o SDK do Devin.
- `scripts/interface.ts`: contrato do domínio, com `SessionMemory` como aggregate root e `absorb` como único comando.
- `resources/prompt.md`: prompt versionado da extração.
