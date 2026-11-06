#!/bin/bash
# window.sh: the agent's only door to the native dev-console window (DevConsole.app).
# This script is the only writer of command.json; the app is the only writer of state.json.
#
#   window.sh open <url>        window.sh reload        window.sh show      window.sh hide
#   window.sh resize <w> <h>    window.sh dock left|right
#   window.sh eval '<js>'       window.sh status        window.sh wait
#   window.sh install           window.sh quit
#
# Every command except status/wait/install/quit sends one command with the next id and returns at
# once; `wait` blocks until the app has applied it (5 s at most) and prints state.json.
# Env: DEV_CONSOLE_WINDOW_STATE_DIR overrides the state directory (tests).
set -euo pipefail

STATE_DIR="${DEV_CONSOLE_WINDOW_STATE_DIR:-$HOME/.local/state/dev-console-window}"
STATE_FILE="$STATE_DIR/state.json"
COMMAND_FILE="$STATE_DIR/command.json"
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"

die() { echo "window: $*" >&2; exit 1; }
need_jq() { command -v jq >/dev/null 2>&1 || die "jq not found (brew install jq)"; }

# int_of <file> <jq field>: the field as an integer, 0 when missing or broken
int_of() {
  local v=""
  [[ -f "$1" ]] && v="$(jq -r "$2 // 0" "$1" 2>/dev/null || true)"
  [[ "$v" =~ ^[0-9]+$ ]] && echo "$v" || echo 0
}

# send <action> [extra-json]: writes command.json atomically with the next id.
# The id is above both the last one sent and the last one the app applied, so it always increments.
send() {
  need_jq
  local action="$1" extra="${2:-}"
  [[ -n "$extra" ]] || extra='{}'
  mkdir -p "$STATE_DIR"
  local sent applied id tmp
  sent="$(int_of "$COMMAND_FILE" .id)"
  applied="$(int_of "$STATE_FILE" .last_command_id)"
  id=$(( (sent > applied ? sent : applied) + 1 ))
  tmp="$(mktemp "$STATE_DIR/.command.XXXXXX")"
  jq -n --argjson id "$id" --arg action "$action" --argjson now "$(date +%s)" --argjson extra "$extra" \
    '{id: $id, action: $action, updated_at: $now} + $extra' > "$tmp" || { rm -f "$tmp"; die "could not write the command"; }
  mv "$tmp" "$COMMAND_FILE"
  echo "sent $id $action"
}

cmd_open() {
  local url="${1:-}"
  [[ "$url" == *://* ]] || die "open needs a url with a scheme (http://127.0.0.1:5057/)"
  send open "$(jq -n --arg url "$url" '{url: $url}')"
}

cmd_resize() {
  [[ "${1:-}" =~ ^[0-9]{2,5}$ && "${2:-}" =~ ^[0-9]{2,5}$ ]] || die "resize needs a width and a height in points (resize 1200 900)"
  send resize "$(jq -n --argjson w "$((10#$1))" --argjson h "$((10#$2))" '{width: $w, height: $h}')"
}

cmd_dock() {
  case "${1:-}" in
    left|right) send dock "$(jq -n --arg side "$1" '{side: $side}')" ;;
    *) die "dock needs left or right" ;;
  esac
}

cmd_eval() {
  [[ -n "${1:-}" ]] || die "eval needs the js to run"
  send eval "$(jq -n --arg js "$1" '{js: $js}')"
}

cmd_status() {
  need_jq
  [[ -f "$STATE_FILE" ]] || die "no state yet (is the app running? window.sh install)"
  cat "$STATE_FILE"
}

# wait: the only loop allowed. 0.1 s steps, capped at 5 s.
cmd_wait() {
  need_jq
  local target; target="$(int_of "$COMMAND_FILE" .id)"
  (( target > 0 )) || die "nothing sent yet"
  local i
  for (( i = 0; i < 50; i++ )); do
    if (( $(int_of "$STATE_FILE" .last_command_id) >= target )); then
      cat "$STATE_FILE"
      return 0
    fi
    sleep 0.1
  done
  [[ -f "$STATE_FILE" ]] && cat "$STATE_FILE"
  die "timeout: command $target not applied in 5 s (is the app running? window.sh install)"
}

cmd_quit() {
  pkill -x DevConsole 2>/dev/null && echo "app quit" || echo "app was not running"
}

cmd_install() {
  [[ "$(uname)" == Darwin ]] || die "install needs macOS"
  "$SELF_DIR/../app/build-app.sh"
  cmd_quit >/dev/null
  mkdir -p "$HOME/Applications"
  ditto "$SELF_DIR/../app/build/DevConsole.app" "$HOME/Applications/DevConsole.app"
  open "$HOME/Applications/DevConsole.app"
  echo "installed ~/Applications/DevConsole.app"
}

case "${1:-}" in
  open)    shift; cmd_open "$@" ;;
  reload)  send reload ;;
  show)    send show ;;
  hide)    send hide ;;
  resize)  shift; cmd_resize "$@" ;;
  dock)    shift; cmd_dock "$@" ;;
  eval)    shift; cmd_eval "$@" ;;
  status)  cmd_status ;;
  wait)    cmd_wait ;;
  install) cmd_install ;;
  quit)    cmd_quit ;;
  *) die "usage: window.sh open <url> | reload | show | hide | resize <w> <h> | dock left|right | eval '<js>' | status | wait | install | quit" ;;
esac
