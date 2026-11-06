#!/usr/bin/env bash
# Entry point of the cost-track skill: every harness calls this; the logic is costs.py (uv, PEP 723).
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in /*) ;; *) SOURCE="$LINK_DIR/$SOURCE" ;; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"

command -v uv >/dev/null 2>&1 || { echo "costs.sh: uv not found (install: https://docs.astral.sh/uv/)" >&2; exit 127; }

[ "${1:-}" = "help" ] && set -- --help
[ $# -gt 0 ] || set -- --help

case "$1" in
  tmux-focus|tmux-install|tmux-uninstall|status) export COSTS_SH="$DIR/costs.sh"; exec uv run --quiet --script "$DIR/tmux_focus.py" "$@" ;;
esac

exec uv run --quiet --script "$DIR/costs.py" "$@"
