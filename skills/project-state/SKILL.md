---
name: project-state
description: >-
  Use before changing any repo or dev-console domain: read the project's declared state and work by its rules.
  draft (the default, no file = draft): edit straight on main, commit and push, no PR, no worktree, no screenshot for
  approval; speed is the goal. live: the guardrails (branch, PR, screenshots approved before merge). Triggers "estado do
  projeto", "isso é draft", "passa para live", "project state", "pode ir direto na main?".
version: 0.1.0
---

# project-state

A project declares its state in a `.project-state` file at the repo root (one word). **No file = `draft`.**

```sh
scripts/state.sh get [<repo dir>]                 # prints draft|live (default: the git root of the current folder)
scripts/state.sh set <draft|live> [<repo dir>]    # writes .project-state; commit it with the change
```

| state | how the agent works |
|---|---|
| `draft` | Edit on `main` of the clone in use, commit, push. No branch, no PR, no worktree, no screenshot waiting for approval, no subagent unless the work is big. Show the result after, not before. |
| `live` | The house's guardrails: one worktree per task (`wt`), PR by `gh-app`, screenshots at his window before merge for any UI change. |

- A rule of another skill that asks for a PR, a worktree or approval before merge (dev-console, como-trabalhamos)
  applies only to `live` projects. In `draft` it is skipped.
- Moving a project to `live` is the owner's call; never promote it yourself.
- In force in any state: the 4 cases that wait for the owner (money, login, publishing outward, deleting), and never
  touching what another agent created.
