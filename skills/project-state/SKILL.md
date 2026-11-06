---
name: project-state
description: >-
  MUST LOAD THIS SKILL AT THE START OF ANY SESSION, before the first reply, to get the project's stage (draft or
  live): it sets how every change in this session ships. Also invoke it before running `git commit`, `git push`, `git checkout -b`, `gh pr create` or a merge,
  before creating a worktree for a change, and whenever the user asks whether to open a PR or go straight to main.
  It answers PR or main for the current repo, and the answer is usually main: every repo of the owner is a draft
  unless its root has a `.project-state` file saying `live`. Draft = commit and push straight to main, no branch, no
  PR, no approval wait. Its answer wins over generic habits ("a PR is cheap") and over other skills' PR rules.
  Triggers "commita", "commit", "push", "abre o PR", "PR ou main?", "precisa de PR?", "merge", "estado do projeto",
  "draft", "live".
version: 0.1.3
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
