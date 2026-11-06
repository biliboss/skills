# Changelog

Todas as mudanças do skill `tmux`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added
- `scripts/lib.sh`: binário do tmux pelo caminho (`TMUX_BIN`, `/opt/homebrew/bin/tmux`, `command -v`), `TMUX_SOCKET` para um servidor privado e o resolvedor de alvos por igualdade exata (`%id`, janela, `sessão:janela`, `sessão:janela.pane`), que lista os candidatos quando não acha ou é ambíguo.
- `scripts/pane.sh`: `read`, `send` (texto literal, fim conferido antes do Enter, várias linhas por paste-buffer, `--` e `--stdin`), `key` e `wait` (`--text` ou `--idle`, prazo obrigatório).
- `scripts/win.sh`: `list` (tabela ou `--json`), `new` (sem roubar o foco, recusa nome repetido) e `rename`.
- `scripts/test.sh`: 34 casos num servidor tmux privado.
