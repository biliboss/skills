#!/usr/bin/env bash
# SessionStart hook: one short line with the repo's stage. Silent outside git; never fails the session.
r="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
s=""
if [ -f "$r/.project-state" ]; then s="$(tr -d '[:space:]' < "$r/.project-state")"; fi
if [ "${s:-draft}" = "live" ]; then
  echo "Project stage: live. Branch and PR; merge after approval."
else
  echo "Project stage: draft. Commit and push straight to main, without asking."
fi
exit 0
