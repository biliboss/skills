#!/usr/bin/env bash
# Entry point of the task-backbrief skill: every harness calls this; the logic is tasks.py (uv, PEP 723).
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in /*) ;; *) SOURCE="$LINK_DIR/$SOURCE" ;; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"

command -v uv >/dev/null 2>&1 || { echo "tasks.sh: uv not found (install: https://docs.astral.sh/uv/)" >&2; exit 127; }

[ "${1:-}" = "help" ] && set -- --help
[ $# -gt 0 ] || set -- --help

exec uv run --quiet --script "$DIR/tasks.py" "$@"
