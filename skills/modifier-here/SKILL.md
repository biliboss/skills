---
name: modifier-here
description: "Use when a request ends in --here. Do it in this session, no subagent."
metadata:
  version: 0.1.0
---

# modifier-here

A request with `--here` ("merge all open PR --here", "corrige o título --here") runs **in this session, by the agent
itself**: no subagent, no thread, no delegation, no other pane. The owner asks for it when the work is short and the
context is already here, so a subagent only adds a cold start and a hand-off. The flag borrows Hermes's
`/branch --here` (act on the current chat instead of opening another) — see [README](README.md).

## Steps

1. **Strip the flag** and read the rest as the request.
2. **Do it here**, with your own tools: plan, then batch the work into as few calls as possible (one scratch `.sh` per
   step). The house rules that send code to subagents (code changes, anything over 2 minutes) are suspended for this
   request only; every other rule holds: the owner's four decisions (money, login, publishing outward, deleting), no
   secrets in chat, `uv` for Python, one card per piece of work, never move his tmux focus.
3. **Stay in the turn until it is done**, then report the result in the first line. If it turns out long (well past
   ~10 minutes of work) say so once and ask whether to keep going here or hand it off; never switch on your own.
4. **No flag, no change**: without `--here` the usual triage applies (short here, long to subagents or a thread).

## Pitfalls

- **`--here` is about who does the work, not about scope.** "merge all --here" still means all; decide what "all"
  covers with the usual care (a client's repo, others' PRs, drafts) and say what was left out and why.
- **Land it like any change**: a worktree off `origin/main` with only your files copied in (the main clone carries
  other sessions' loose edits), `gh-app push`, `gh-app pr create`, squash merge, `wt`/worktree removed, main clone
  pulled with `--autostash`. Run the touched skill's tests first, unless the owner said not to ("sem rodar tests"):
  then land without them and say in the PR and the report which tests still expect the old behaviour.
- **The owner corrects mid-turn**: a message that reverses part of the request ("não, da thread atual, não da aba")
  replaces it at once; ask one line through the ask tool when two readings remain, then build the one he picked.
- **A blocked step stays blocked.** Branch protection, conflicts or a required review are named in the report with the
  way around (rebase, approve, `--admin` when the owner ordered it), not silently skipped.
