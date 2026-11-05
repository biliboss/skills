#!/bin/bash
# timer.sh: the engine's only door to the menu bar timer.
# The app (StatusTimer.app) only displays the state file; this script is its only writer.
#
#   timer.sh start <dur> [label]   timer.sh pause    timer.sh resume
#   timer.sh add <dur>             timer.sh stop     timer.sh status
#   timer.sh install               timer.sh quit
#
# <dur>: 25 (minutes), 25m, 90s, 1h, 1:30 (mm:ss).
# Env: STATUS_TIMER_STATE_DIR overrides the state directory (tests).
#      STATUS_TIMER_NOW overrides the clock, epoch seconds (tests).
set -euo pipefail

STATE_DIR="${STATUS_TIMER_STATE_DIR:-$HOME/.local/state/status-timer}"
STATE_FILE="$STATE_DIR/state.json"
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"

die() { echo "timer: $*" >&2; exit 1; }
now() { echo "${STATUS_TIMER_NOW:-$(date +%s)}"; }

need_jq() { command -v jq >/dev/null 2>&1 || die "jq not found (brew install jq)"; }

# parse_duration <text> -> seconds on stdout; nonzero on bad input
parse_duration() {
  local t="$1" n unit=m
  [[ -n "$t" ]] || return 1
  if [[ "$t" =~ ^([0-9]{1,6}):([0-9]{1,2})$ ]]; then
    local m="${BASH_REMATCH[1]}" s="${BASH_REMATCH[2]}"
    (( 10#$s < 60 )) || return 1
    n=$(( 10#$m * 60 + 10#$s ))
  elif [[ "$t" =~ ^([0-9]{1,6})([smh]?)$ ]]; then
    n=$((10#${BASH_REMATCH[1]}))
    unit="${BASH_REMATCH[2]:-m}"
    case "$unit" in
      s) ;;
      m) n=$(( n * 60 )) ;;
      h) n=$(( n * 3600 )) ;;
    esac
  else
    return 1
  fi
  (( n > 0 )) || return 1
  echo "$n"
}

dur_or_die() {
  parse_duration "${1:-}" || die "bad duration '${1:-}' (use 25, 25m, 90s, 1h or 1:30)"
}

fmt() { # seconds -> MM:SS or H:MM:SS
  local t=$1
  (( t < 0 )) && t=0
  if (( t >= 3600 )); then
    printf '%d:%02d:%02d' $((t / 3600)) $((t % 3600 / 60)) $((t % 60))
  else
    printf '%02d:%02d' $((t / 60)) $((t % 60))
  fi
}

# read_field <jq filter> <default>
read_field() {
  if [[ -f "$STATE_FILE" ]]; then
    jq -r "$1 // empty" "$STATE_FILE" 2>/dev/null || true
  fi
}

cur_status() { local s; s="$(read_field .status)"; echo "${s:-idle}"; }

# publish <verb>: best effort NATS event, never fails
publish() {
  command -v nats >/dev/null 2>&1 || return 0
  {
    timeout 1 nats -s 127.0.0.1:4222 pub "mesa.timer.$1" "$(cat "$STATE_FILE")" >/dev/null 2>&1
  } || true
}

# write_state <status> <ends_at|""> <remaining|""> <label>
write_state() {
  need_jq
  mkdir -p "$STATE_DIR"
  local tmp
  tmp="$(mktemp "$STATE_DIR/.state.XXXXXX")"
  jq -n --arg status "$1" --arg ends "$2" --arg rem "$3" --arg label "$4" --argjson now "$(now)" '{
    status: $status,
    ends_at: (if $ends == "" then null else ($ends | tonumber) end),
    remaining: (if $rem == "" then null else ($rem | tonumber) end),
    label: $label,
    updated_at: $now
  }' > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

cmd_start() {
  local d; d="$(dur_or_die "${1:-}")"
  local label="${2:-}"
  write_state running "$(( $(now) + d ))" "" "$label"
  publish start
  echo "started $(fmt "$d")${label:+ $label}"
}

cmd_pause() {
  need_jq
  [[ "$(cur_status)" == running ]] || die "nothing running to pause"
  local ends rem; ends="$(read_field .ends_at)"
  rem=$(( ends - $(now) )); (( rem < 0 )) && rem=0
  write_state paused "" "$rem" "$(read_field .label)"
  publish pause
  echo "paused at $(fmt "$rem")"
}

cmd_resume() {
  need_jq
  [[ "$(cur_status)" == paused ]] || die "nothing paused to resume"
  local rem; rem="$(read_field .remaining)"
  write_state running "$(( $(now) + rem ))" "" "$(read_field .label)"
  publish resume
  echo "resumed with $(fmt "$rem")"
}

cmd_add() {
  need_jq
  local d; d="$(dur_or_die "${1:-}")"
  local label; label="$(read_field .label)"
  case "$(cur_status)" in
    running)
      local ends n; ends="$(read_field .ends_at)"; n="$(now)"
      (( ends < n )) && ends=$n
      write_state running "$(( ends + d ))" "" "$label"
      publish add
      echo "added $(fmt "$d"), $(fmt $(( ends + d - n ))) left" ;;
    paused)
      local rem; rem=$(( $(read_field .remaining) + d ))
      write_state paused "" "$rem" "$label"
      publish add
      echo "added $(fmt "$d"), paused at $(fmt "$rem")" ;;
    *) die "no timer to add time to (use start)" ;;
  esac
}

cmd_stop() {
  write_state idle "" "" ""
  publish stop
  echo "stopped"
}

cmd_status() {
  need_jq
  local label; label="$(read_field .label)"
  case "$(cur_status)" in
    running)
      local left=$(( $(read_field .ends_at) - $(now) ))
      echo "$(fmt "$left")${label:+ $label}" ;;
    paused)
      echo "paused $(fmt "$(read_field .remaining)")${label:+ $label}" ;;
    *) echo "idle" ;;
  esac
}

cmd_quit() {
  pkill -x StatusTimer 2>/dev/null && echo "app quit" || echo "app was not running"
}

cmd_install() {
  [[ "$(uname)" == Darwin ]] || die "install needs macOS"
  "$SELF_DIR/../app/build-app.sh"
  cmd_quit >/dev/null
  mkdir -p "$HOME/Applications"
  ditto "$SELF_DIR/../app/build/StatusTimer.app" "$HOME/Applications/StatusTimer.app"
  open "$HOME/Applications/StatusTimer.app"
  echo "installed ~/Applications/StatusTimer.app"
}

case "${1:-}" in
  start)   shift; cmd_start "$@" ;;
  pause)   cmd_pause ;;
  resume)  cmd_resume ;;
  add)     shift; cmd_add "$@" ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  install) cmd_install ;;
  quit)    cmd_quit ;;
  *) die "usage: timer.sh start <dur> [label] | pause | resume | add <dur> | stop | status | install | quit" ;;
esac
