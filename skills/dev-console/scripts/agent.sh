#!/bin/bash
# agent.sh: one door for an agent to the native dev-console window and its flight recorder.
#
#   agent.sh now            the last recorded navigation (url, domain, module, event, widget, errors, shot)
#   agent.sh history [n]    the last n lines (default 5), newest last
#   agent.sh shot           ask the app for a fresh snapshot, print its line (then look at the PNG)
#   agent.sh open <url>     load a URL in the app (window.sh open: no domain claim) and print the new line
#   agent.sh eval '<js>'    window.sh eval + wait: prints the value
#   agent.sh status         window.sh status (url, title, size, last result)
#
# The recorder is <DEV_CONSOLE_RECORDER_DIR:-~/.local/state/dev-console/recorder>/events.jsonl, written by the app only
# (the last 20 lines, a PNG each in shots/). Add --owner <name> first to drive that owner's own window.
# Nothing leaves the machine. Needs jq.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
WINDOW=("$SELF_DIR/window.sh")
if [[ "${1:-}" == --owner ]]; then WINDOW+=(--owner "${2:-}"); shift 2; fi
REC_DIR="${DEV_CONSOLE_RECORDER_DIR:-$HOME/.local/state/dev-console/recorder}"
EVENTS="$REC_DIR/events.jsonl"

die() { echo "agent: $*" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || die "jq not found (brew install jq)"

# last_at: the `at` of the newest line, empty when there is none
last_at() { [[ -s "$EVENTS" ]] && tail -n 1 "$EVENTS" | jq -r '.at // empty' 2>/dev/null || true; }

# show: stdin is one JSON line per row; prints the essentials
show() {
  jq -r '"at      \(.at)\nurl     \(.url // "-")\ndomain  \(.domain // "-")\nmodule  \(.module // "-")\nevent   \(.event // "-")\nwidget  \(.widget // "-")\nsize    \(.width)x\(.height)\nerrors  \((.errors // []) | length)\(if ((.errors // []) | length) > 0 then "  first: " + (.errors[0] | .[0:160]) else "" end)\nshot    \(.shot // "-")"'
}

cmd_now() {
  [[ -s "$EVENTS" ]] || die "no lines yet in $EVENTS (is DevConsole.app running? window.sh install)"
  tail -n 1 "$EVENTS" | show
}

cmd_history() {
  local n="${1:-5}"
  [[ "$n" =~ ^[0-9]+$ ]] && (( n >= 1 && n <= 20 )) || die "history needs a number from 1 to 20"
  [[ -s "$EVENTS" ]] || die "no lines yet in $EVENTS"
  tail -n "$n" "$EVENTS" | show | sed 's/^at  /--\nat  /'
}

# wait_new <previous at>: the only loop here, 0.2 s steps, 10 s at most (the page reports after 0.5 s, then the snapshot)
wait_new() {
  local before="$1" i
  for (( i = 0; i < 50; i++ )); do
    [[ "$(last_at)" != "$before" ]] && return 0
    sleep 0.2
  done
  return 1
}

cmd_shot() {
  "${WINDOW[@]}" running || die "the app is not running: use the console's GET /agent/shot (headless fallback) or check.sh <url> --shot out.png"
  local before; before="$(last_at)"
  "${WINDOW[@]}" shot >/dev/null
  local state result
  state="$("${WINDOW[@]}" wait)" || die "the app did not answer the shot command"
  result="$(jq -r '.last_result // ""' <<<"$state")"
  [[ "$result" != error:* ]] || die "$result"
  wait_new "$before" || die "no new line was recorded"
  cmd_now
}

cmd_open() {
  local url="${1:-}"
  [[ "$url" == *://* ]] || die "open needs a url with a scheme (http://127.0.0.1:5057/)"
  local before; before="$(last_at)"
  "${WINDOW[@]}" open "$url" >/dev/null
  "${WINDOW[@]}" wait >/dev/null || die "the app did not apply the open (is it running?)"
  if wait_new "$before"; then cmd_now; else echo "(no new line: the page did not change state)"; cmd_now; fi
}

cmd_eval() {
  [[ -n "${1:-}" ]] || die "eval needs the js to run"
  "${WINDOW[@]}" eval "$1" >/dev/null
  "${WINDOW[@]}" wait | jq -r '.last_result'
}

case "${1:-}" in
  now)     cmd_now ;;
  history) shift; cmd_history "$@" ;;
  shot)    cmd_shot ;;
  open)    shift; cmd_open "$@" ;;
  eval)    shift; cmd_eval "$@" ;;
  status)  "${WINDOW[@]}" status ;;
  *) die "usage: agent.sh [--owner <name>] now | history [n] | shot | open <url> | eval '<js>' | status" ;;
esac
