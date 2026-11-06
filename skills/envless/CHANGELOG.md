# Changelog

Todas as mudanças do skill `envless`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-11-06

### Changed

- `acha-chave.sh` (find a key by name without a value), receiving a secret from another person via `vigia-copiar.py`, `migrate` for a plain `.env`, GitHub Actions secrets cannot be read back.

## [0.1.0] - 2026-11-04

### Added
- O envless como o caminho do segredo: achar o cofre e a chave sem valor (`ls secrets/`, `list`), usar pelo `exec`, guardar pelo stdin (`set`), `get` só com `--confirm` e para um pipe, `migrate` e `init`.
- As armadilhas medidas na v0.2.1: o envless não sobe de pasta (fora da raiz, `list` volta vazio e `exec` roda sem os segredos, com exit 0) e um `--env` inexistente também volta vazio com exit 0.
- Quando usar o CLI e quando o `envless mcp` (cliente sem shell), e por que o `get` e o `set` do MCP põem o valor na conversa.
