# Changelog

Todas as mudanças do skill `tmux`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-11-06

### Changed

- `agent-state.sh` publishes the window's state on every write (thread-state.sh, in the background), so `thread.sh watch` sees ●◆✓ live.

## [0.6.0] - 2026-11-06

### Added

- `pane.sh do <alvo> k=<Tecla> t=<texto> s=<seg>... [--read N]`: uma interação inteira num tiro (teclas, texto literal e pausas em ordem, com um respiro entre os passos), e no fim o pane; `--read 0` não lê.

## [0.5.0] - 2026-11-06

### Added

- `agent-state.sh ask|answered` (◆ on bordô, `@ask`) for the Hermes `on_human_input_request/resolved` hooks.

### Changed

- The hooks call `thread.sh sort <pane>` (MRU tab order, debounced) instead of `touch`.

## [0.4.0] - 2026-11-06

### Added

- `agent-state.sh sub+|sub-` (Hermes `subagent_start`/`subagent_stop` hooks; the window is found by `parent_session_id` = the parent's `@hsid`): `@subagents=N`, never below 0. The tab shows one grey Nerd Font glyph (U+F013, `AGENT_STATE_ICON` overrides, e.g. `⚙`) + the count before the name; while N > 0 the turn's end does NOT light ✓ (`@turnended`), which lights when N drops to 0.

## [0.3.0] - 2026-11-06

### Added

- `scripts/agent-state.sh working|done|clear [target]`: a tab shows when its Hermes agent finishes a turn (` ✓ <name> `, white bold on #800020) and clears when the owner enters it. `working` sets `@agent`; `done` sets `@done` + the style/format only if the window is not the one an attached client is looking at. `install` / `uninstall`: indexed hooks `session-window-changed[42]` and `client-session-changed[42]` (live and as a marked block in `~/.tmux.conf`, idempotent) and prints the Hermes `hooks:` snippet. Silent on stdout, always exit 0. `working` and `done` also call `thread.sh touch` (the thread goes to tab 2).
- `scripts/test-agent-state.sh`: 26 cases on a private server (`-L`).

## [0.2.1] - 2026-11-06

### Changed

- Learnings from sessions folded in.

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
