#!/usr/bin/env bash
# The focus: the one pointer of what the owner and the Bili are looking at (console_focus.py, uv, stdlib only).
#   focus.sh set "<text>" --target <kanban|slug|slug/event/Widget|url> [--card <card>] --by gabriel|bili
#   focus.sh back --by gabriel|bili
#   focus.sh show [--json]
# Only the owner's conversation with the Bili moves it: subagents and profiles never call `focus.sh set` or `back`.
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in /*) ;; *) SOURCE="$LINK_DIR/$SOURCE" ;; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"

if ! command -v uv >/dev/null 2>&1; then
  echo "focus.sh: uv not found (install: https://docs.astral.sh/uv/)" >&2
  exit 127
fi

[ $# -gt 0 ] || set -- --help
exec uv run --quiet --script "$DIR/console_focus.py" "$@"
