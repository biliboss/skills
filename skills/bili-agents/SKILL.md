---
name: bili-agents
description: >-
  Operate local coding agents, inspect their state, send scoped work, and collect evidence with the ag-* tools.
  Use for agent setup, delegation, roles, session startup, and the shared voice.
metadata:
  version: 0.1.0
---

# Local agents

Read the selected tool before running it. Code lives in this skill; machine configuration lives in `AG_HOME`.
Run `scripts/ag-doctor --fast` first. Inspect a target with `ag-read` before sending input with `ag-send`.
Use `ag-wait` for completion; a Stop notification alone does not prove completion. Never poll pane contents in a loop.
Keep each coding agent in an isolated worktree. Give it a concrete outcome, permitted paths and verification criteria.
Review its diff and evidence before delivery. Native harness subagents may be used without terminal control;
pass their worktree explicitly and collect their result through the harness mailbox.
Do not operate existing user terminals without authorization. Read [hook-ping](references/hook-ping.md) when wiring notifications.
The older [herdr notes](references/herdr.md) describe an earlier backend; the current scripts use `hc`.

Run `scripts/setup -n` to review installation, then `scripts/setup` when installation is requested.
Run `scripts/session-start.sh` at the beginning of a local session. Treat missing roles or voice configuration as
pending work, never as evidence of a loaded role. Keep one user-facing coordinator voice; workers return evidence
to the coordinator and do not impersonate the owner.
