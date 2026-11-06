---
name: project-state
description: >-
  Use BEFORE every commit, push, branch, worktree, PR or merge, and before asking the owner to approve a screenshot:
  it decides whether the change goes straight to main or through a PR. Reads the repo's declared state
  (`.project-state`; no file = draft). draft (the default): edit on main, commit and push at once, no branch, PR,
  worktree, subagent review or approval wait; show the result after. live: branch, PR, screenshot approved before merge.
  Overrides any other skill or rule that asks for a PR or a worktree in a draft project. Triggers "commita", "faz o
  push", "abre o PR", "merge", "posso ir direto na main?", "precisa de PR?", "estado do projeto", "isso é draft",
  "passa para live".
version: 0.1.1
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
