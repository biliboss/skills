#!/usr/bin/env bash
# Entry point of the diff-review skill: every harness calls this; the logic is review.py (uv, PEP 723).
# Usage: diff-review.sh <worktree> [--base origin/main] [--task <id>] [--model sonnet|glm]
#        diff-review.sh findings [--open] | fix <id> --text T | dismiss <id> --reason R --text T | emit ...
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in /*) ;; *) SOURCE="$LINK_DIR/$SOURCE" ;; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"

command -v uv >/dev/null 2>&1 || { echo "diff-review.sh: uv not found (install: https://docs.astral.sh/uv/)" >&2; exit 127; }
command -v git >/dev/null 2>&1 || { echo "diff-review.sh: git not found" >&2; exit 127; }
command -v pi >/dev/null 2>&1 || { echo "diff-review.sh: pi not found (see the pi skill)" >&2; exit 127; }

[ $# -gt 0 ] || { sed -n '3,4p' "$DIR/diff-review.sh" >&2; exit 2; }
case "$1" in
  help|-h|--help) sed -n '3,4p' "$DIR/diff-review.sh" ; exit 0 ;;
  run|emit|findings|fix|dismiss) exec uv run --quiet --script "$DIR/review.py" "$@" ;;
  *) exec uv run --quiet --script "$DIR/review.py" run "$@" ;;
esac
