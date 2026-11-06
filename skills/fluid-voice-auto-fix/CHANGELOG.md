# Changelog

Todas as mudanças do skill `fluid-voice-auto-fix`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-04

### Added
- `scripts/fix.sh` com `add`, `boost`, `list`, `backup`, `restore` e `scan`; backup e diff antes/depois em toda mudança, e reinício do FluidVoice.
- Guarda de ordem das regras: a forma reescrita vira gatilho da regra multi-palavra.
- `tests/test.sh` com um domínio falso.
