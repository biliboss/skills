# Briefing a subagent so it finishes fast and lands

Measured over ~150 subagent runs: about two thirds of the wall time is the model thinking between tool calls
(~10 s each, the whole context resent), a third is tools. Speed comes from fewer, larger calls and less
re-discovery, not from faster tools. Put these in every brief.

## What the brief carries

- **Project and card first**: `<project> · <goal>`; one card per work, the subagent never creates cards.
- **A file map, not a tour**: the exact files, functions (with line numbers when known), tests and the command that
  checks the work. A brief without it costs ~8 reading calls (~30% of the run) before the first edit.
- **A tool-call budget** (25–45) and "commit early": a checkpoint commit after the first change that passes its test,
  so hitting the iteration cap never loses the work (several runs ended with everything done and nothing committed).
- **Batch reads and checks**: one terminal/execute_code call that reads several files or runs all the checks, not one
  call per file.
- **Landing steps spelled out**: worktree from `origin/main`, versions bumped above main at landing, diff-review, push
  with `gh-app`, PR, merge (or NOT merge, below), remove the worktree, delete the squash-merged local branch.
- **Screen changes stop at the PR**: anything the owner sees (layout, labels, panels, home, gestures) opens a PR with
  screenshots at his window size and does not merge; he approves by looking.
- **Publishing stays his**: merges that deploy, Cloudflare/DNS, Search Console, deleting unmerged work.

## What the brief forbids

- **Polling a TUI agent** (`pane.sh wait` loops) to see a line appear: one shepherd waited 23 min this way. Send the
  instruction once to the agent and let its result come back as an event.
- **The full test suite of a big repo**: run the tests of the touched files with a bound (10 min); long runs go to a
  services tab with a log the subagent reads.
- **Exporting test env vars** (`KANBAN_DIR`, `COSTS_DIR`, `DEV_CONSOLE_*`) in the shared shell: set them inline per
  command, or the next real write lands in a scratch journal.
- `python3 -c`, heredocs for code, `sleep` to wait, force pushes.

## Version conflicts

Parallel PRs that each bump a skill version, the plugin version and two CHANGELOGs collide on the same lines and eat
the end of runs. Until versions are generated at merge, land parallel PRs one at a time and tell each brief that main
may move: "rebase and bump above main's version at landing".
