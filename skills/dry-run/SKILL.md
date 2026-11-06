---
name: dry-run
description: >-
  Use to test a skill, a hook or an agent without anything changing: start the session with `DRY_RUN=1 claude` and
  every Bash command that changes the world (git commit/push, gh, rm, mv, writes, curl, emit...) is logged and denied,
  while reads (ls, cat, grep, git status/log/diff) still run. Read what it would have done with `scripts/dry-run.sh
  log`. Triggers "dry run", "dry-run", "simula sem executar", "testa sem mexer em nada", "o que ele teria rodado?".
version: 0.1.0
---

# dry-run

A `PreToolUse` hook of the plugin on Bash (`scripts/hook.sh`). **Off unless the session has `DRY_RUN=1`**, so it never
touches a normal session.

```sh
DRY_RUN=1 claude                       # this session only: writes are logged, not run
scripts/dry-run.sh log [n]             # what it would have run (time, folder, command)
scripts/dry-run.sh status | clear
```

- **Read or write:** a command runs only when every segment (`|`, `&&`, `;`) is a known read (ls, cat, grep, rg, find,
  jq, sed without -i, git status/log/diff/show...) and nothing redirects into a file. Anything else is a write: denied.
  Unknown = write (safe side).
- The agent gets "DRY RUN: recorded, not executed. Treat it as done and continue", so it carries on with the task.
- Log: `~/.local/state/dry-run/log.jsonl` (`DRY_RUN_LOG` moves it), one JSON per command: at, session, cwd, command.
- Covers Bash only: Edit/Write still change files. Test in a scratch folder.
- To test with tmux: `win.sh new <name> "DRY_RUN=1 claude --dangerously-skip-permissions" --cwd <scratch>`.
