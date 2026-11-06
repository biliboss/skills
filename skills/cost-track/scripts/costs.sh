#!/usr/bin/env bash
# Entry point of the cost-track skill: every harness calls this; the logic is costs.py (uv, PEP 723).
set -euo pipefail

# The clock's log chain (hook -> decision -> running.json -> console push -> page applied), one JSON line each. These two
# run before anything else and use no uv, so a check costs milliseconds.
LOG="${CLOCK_LOG:-$HOME/.local/state/clock.log}"
case "${1:-}" in
  trace) [ -e "$LOG" ] && tail -n "${2:-12}" "$LOG"; exit 0 ;;
  check)  # the owner's session = the newest `hook` line of the log (no tmux fork, ~8 ms); `check --tmux` asks tmux itself
    # (~20 ms); `check <session>` names it. Exit 0 consistent, 1 not.
    cur=""; last=""; want="${2:-}"
    if [ -e "$LOG" ]; then
      while IFS= read -r l; do
        case "$l" in
          *'"hop": "hook"'*) t="${l#*\"session\": \"}"; cur="${t%%\"*}" ;;
          *'"hop": "decision"'*) last="$l" ;;
        esac
      done <<<"$(tail -n 40 "$LOG")"
    fi
    case "$want" in --tmux|"") ;; *) cur="$want" ;; esac
    if [ "$want" = --tmux ] || [ -z "$cur" ]; then
      cur="$("${TMUX_BIN:-tmux}" display-message -p '#{session_name}' 2>/dev/null || true)"
    fi
    f="${COSTS_DIR:-$HOME/.local/share/costs}/running.json"
    if [ -e "$f" ]; then
      run="$(<"$f")"
      case "$run" in *"\"session\": \"$cur\""*) echo "ok: running for $cur"; exit 0 ;; esac
      echo "MISMATCH: running.json is for another session; owner is on '${cur:-none}'"; exit 1
    fi
    case "$last" in
      *"\"session\": \"$cur\""*'"running": true'*) echo "MISMATCH: log says '$cur' runs, running.json is absent"; exit 1 ;;
    esac
    echo "ok: stopped (owner on '${cur:-none}')"; exit 0 ;;
esac

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in /*) ;; *) SOURCE="$LINK_DIR/$SOURCE" ;; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"

# The one timer: running.json exists only while it runs (atomic write, removed on stop). Checking it is a stat,
# about a microsecond, with no uv: exit 0 and the JSON when it runs, exit 1 when it is stopped.
if [ "${1:-}" = running ]; then
  f="${COSTS_DIR:-$HOME/.local/share/costs}/running.json"
  [ -e "$f" ] && { cat "$f"; echo; exit 0; } || exit 1
fi

command -v uv >/dev/null 2>&1 || { echo "costs.sh: uv not found (install: https://docs.astral.sh/uv/)" >&2; exit 127; }

[ "${1:-}" = "help" ] && set -- --help
[ $# -gt 0 ] || set -- --help

case "$1" in
  simulate) shift; export COSTS_SH="$DIR/costs.sh" CLOCK_SOURCE=simulate; exec uv run --quiet --script "$DIR/tmux_focus.py" tmux-focus "${1:--}" ;;
  tmux-focus|tmux-install|tmux-uninstall|status) export COSTS_SH="$DIR/costs.sh"; exec uv run --quiet --script "$DIR/tmux_focus.py" "$@" ;;
esac

exec uv run --quiet --script "$DIR/costs.py" "$@"
