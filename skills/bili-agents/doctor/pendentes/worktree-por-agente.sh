#!/usr/bin/env bash
# what: ag-new --worktree creates a worktree of its own for the agent (a dry run with -n shows the branch)
[ -x "$BIN/ag-new" ] || { echo "ag-new does not exist yet"; exit 1; }
out="$("$BIN/ag-new" -n demo-project --papel hipster --projeto demo-project --worktree "$(dirname "$(dirname "$AG_SKILL")")" 2>&1)" || { echo "dry run failed: $out"; exit 1; }
case "$out" in *"git worktree add"*run/demo-project*) echo "dry run shows git worktree add on branch run/demo-project" ;; *) echo "dry run does not show the worktree: $out"; exit 1 ;; esac
