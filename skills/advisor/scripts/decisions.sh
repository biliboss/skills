#!/usr/bin/env bash
# Read the journal before deciding whether to call the advisor.
#   decisions.sh recent <task-kind> --moment <m> [--last N]   the last N decisions (default 10) of that kind AT that moment
#   decisions.sh list [<thread>]                              the raw decisions, one per row
# The key is (task-kind, moment): the plan usually gets "segue" while the delivery check is what catches things, so a
# kind's calls are never pooled across moments. The rule `recent` prints:
#   CHAME  when the records show the advice changing course, or a missed call;
#   PULE   only with 3 or more RATED calls of that kind and moment, none of which changed course, no `missed`, and the
#          moment is not `irreversivel` (an action that cannot be undone never skips);
#   CHAME  otherwise. Too little history proves nothing, and a window of only skips has no calls left in it, so the rule
#          falls back to CHAME on purpose: skipping must be re-earned by calls, never by more skipping.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

cmd_recent() {
  local kind="${1:-}" moment="" n=10
  shift || true
  [ -n "$kind" ] || die "usage: decisions.sh recent <task-kind> --moment <m> [--last N]"
  kind_ok "$kind"
  while [ $# -gt 0 ]; do
    [ $# -ge 2 ] || die "$1 needs a value"
    case "$1" in
      --moment) moment="$2" ;;
      --last) [[ "$2" =~ ^[0-9]+$ ]] || die "--last needs a number"; n="$2" ;;
      *) die "unknown option: $1" ;;
    esac
    shift 2
  done
  [ -n "$moment" ] || die "--moment is required: the rule reads each moment on its own"
  moment_ok "$moment"
  if [ ! -f "$decisions" ]; then
    echo "($kind, $moment): no decisions recorded yet -> CHAME (nothing proves a skip)"
    return
  fi
  # the threads of the last N decisions of this (kind, moment), then what the journal says about them at that moment
  jq -rs --arg k "$kind" --arg m "$moment" --argjson n "$n" '
    ([ .[] | select(.event=="advisor.decided" and .value.task_kind==$k and .value.moment==$m) ] | .[-$n:]) as $d
    | ($d | map(.value.thread) | unique) as $th
    | [ .[] | select(.event=="advice.rated"   and .value.moment==$m and (.value.thread as $t | $th | index($t))) ] as $rated
    | [ .[] | select(.event=="advisor.missed" and .value.moment==$m and (.value.thread as $t | $th | index($t))) ] as $missed
    | ($d | map(select(.value.called)) | length) as $called
    | ($rated | map(select(.value.changed_course)) | length) as $changed
    | ($rated | map(select(.value.useful)) | length) as $useful
    | ($missed | length) as $miss
    | "(\($k), \($m)): \($d|length) decisions (\($called) calls, \($d|length - $called) skips), "
      + "\($rated|length) rated: \($changed) changed course, \($useful) useful; \($miss) missed",
      ( if   $m == "irreversivel" then "-> CHAME (an action that cannot be undone never skips)"
        elif $miss > 0 or $changed > 0 then "-> CHAME (the records show the advice changing course, or a missed call)"
        elif $called >= 3 and ($rated|length) >= 3 then "-> PULE (3 or more rated calls of this kind and moment, none changed course)"
        else "-> CHAME (PULE needs 3 rated calls of this kind and moment; there are \($rated|length))" end ),
      ( $missed[] | "   missed: \(.value.what_went_wrong)" ),
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
  *) echo "usage: decisions.sh recent <task-kind> --moment <m> [--last N] | list [<thread>]" >&2; exit 2 ;;
esac
