# Changelog

Todas as mudanças do skill `tmux`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-06

### Added

- `scripts/run.sh`: processo longo (servidor, watcher, suite) numa sessão tmux com o nome da worktree dona, marcada (`@procs`, `@owner`), uma janela por nome, log em `$PROCS_DIR/<sessão>/<nome>.log` com `exit=<código>` no fim. `start` (`--cwd`, `--owner`, `--low` com `taskpolicy -b` ou `nice -n 10`, `--slot` com vagas globais por `mkdir` atômico e vaga de pid morto retomada, `--restart` por `respawn-pane -k`), `ls [--json]`, `log`, `stop` (recusa sessão sem a marca; `--owner DIR`), `reap [--dry-run]`, `install-reaper` / `uninstall-reaper` (launchd, 60 s).
- SKILL.md: seção "Processos longos" (a regra, o snippet do hook `post-remove` do Worktrunk, as armadilhas) e gatilhos novos na descrição.
- `scripts/test.sh`: casos novos do `run.sh` (servidor privado, `PROCS_DIR` e repos/worktrees temporários).

## [0.1.1] - 2026-11-06

### Changed

- Armadilha nova: ler o pane antes de mandar tecla; num agente vivo (a janela virou do dono) nunca `/quit` nem comando de shell; reabrir numa janela nova.

## [0.1.0] - 2026-11-06

### Added

- Alvo `TNN` (o id da casa, a opção `@tnn` do pane), por igualdade exata. Sem achar, cai na regra do nome, e o mesmo id em dois panes é erro.
- `scripts/lib.sh`: binário do tmux pelo caminho (`TMUX_BIN`, `/opt/homebrew/bin/tmux`, `command -v`), `TMUX_SOCKET` para um servidor privado e o resolvedor de alvos por igualdade exata (`%id`, janela, `sessão:janela`, `sessão:janela.pane`), que lista os candidatos quando não acha ou é ambíguo.
- `scripts/pane.sh`: `read`, `send` (texto literal, fim conferido antes do Enter, várias linhas por paste-buffer, `--` e `--stdin`), `key` e `wait` (`--text` ou `--idle`, prazo obrigatório).
- `scripts/win.sh`: `list` (tabela ou `--json`), `new` (sem roubar o foco, recusa nome repetido) e `rename`.
- `scripts/test.sh`: 34 casos num servidor tmux privado.
