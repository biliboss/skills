#!/usr/bin/env bash
# SessionStart hook: one short line with the repo's stage. Silent outside git; never fails the session.
r="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
s=""
if [ -f "$r/.project-state" ]; then s="$(tr -d '[:space:]' < "$r/.project-state")"; fi
if [ "${s:-draft}" = "live" ]; then
  echo "Project stage: live (branch and PR)."
else
  echo "Project stage: draft (commit straight to main)."
fi
exit 0
