#!/usr/bin/env bash
# Read the journal before deciding whether to call the advisor.
#   decisions.sh recent <task-kind> [--last N]     summary of the last N decisions of that kind (default 10)
#   decisions.sh list [<thread>]                   the raw decisions, one per row
# The rule `recent` prints: CHAME when records of the same kind show the advice changing course, or when a call was
# missed; PULE when the last calls of that kind only said "segue"; with too little history, CHAME (nothing proves a skip).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

cmd_recent() {
  local kind="${1:-}" n=10
  shift || true
  [ -n "$kind" ] || die "usage: decisions.sh recent <task-kind> [--last N]"
  while [ $# -gt 0 ]; do
    [ "$1" = --last ] && [ $# -ge 2 ] && [[ "$2" =~ ^[0-9]+$ ]] || die "unknown option: $1"
    n="$2"; shift 2
  done
  if [ ! -f "$decisions" ]; then
    echo "task-kind $kind: no decisions recorded yet -> CHAME (nothing proves a skip)"
    return
  fi
  # the threads of the last N decisions of this kind, then everything the journal says about them
  jq -rs --arg k "$kind" --argjson n "$n" '
    def threads: [ .[] | select(.event=="advisor.decided" and .value.task_kind==$k) ] | .[-$n:];
    (threads) as $d
    | ($d | map(.value.thread) | unique) as $th
    | [ .[] | select(.event=="advice.rated"   and (.value.thread as $t | $th | index($t))) ] as $rated
    | [ .[] | select(.event=="advisor.missed" and (.value.thread as $t | $th | index($t))) ] as $missed
    | ($d | map(select(.value.called)) | length) as $called
    | ($rated | map(select(.value.changed_course)) | length) as $changed
    | ($rated | map(select(.value.useful)) | length) as $useful
    | ($missed | length) as $miss
    | "task-kind \($k): \($d|length) decisions (\($called) calls, \($d|length - $called) skips), "
      + "\($rated|length) rated: \($changed) changed course, \($useful) useful; \($miss) missed",
      ( if   $miss > 0 or $changed > 0 then "-> CHAME (the records show the advice changing course, or a missed call)"
        elif $called >= 2 and ($rated|length) >= 2 then "-> PULE (the last calls of this kind only said segue)"
        else "-> CHAME (too little history to skip)" end ),
      ( $missed[] | "   missed: \(.value.moment) \(.value.what_went_wrong)" ),
      ( $rated[]  | select(.value.changed_course) | "   changed course: \(.value.note)" )
  ' "$decisions"
}

cmd_list() {
  [ -f "$decisions" ] || die "no decisions yet: $decisions"
  jq -r --arg th "${1:-}" 'select($th == "" or .value.thread == $th)
    | "\(.at) \(.actor) \(.event) \(.value | tostring | .[0:240])"' "$decisions"
}

case "${1:-}" in
  recent) shift; cmd_recent "$@" ;;
  list) shift; cmd_list "$@" ;;
  *) echo "usage: decisions.sh recent <task-kind> [--last N] | list [<thread>]" >&2; exit 2 ;;
esac
