#!/usr/bin/env bash
# What came of a decision, written to decisions.jsonl.
#   rate.sh rated  <thread> <reply_to> --changed-course true|false --useful true|false --note "..." [--actor <name>]
#       after an answer: did the advice change what you did, was it worth the call (advice.rated)
#   rate.sh missed <thread> --moment plano|travou|terminou|irreversivel|ambiguidade --what "..." [--actor <name>]
#       you did NOT call and it went wrong later (the owner corrected you, a test failed): advisor.missed
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

mode="${1:-}"; shift || true
case "$mode" in
  rated)
    th="${1:-}" re="${2:-}"; shift 2 || true
    [ -n "$th" ] && [ -n "$re" ] || die "usage: rate.sh rated <thread> <reply_to> --changed-course .. --useful .. --note .."
    thread_ok "$th"
    changed="" useful="" note=""
    while [ $# -gt 0 ]; do
      [ $# -ge 2 ] || die "$1 needs a value"
      case "$1" in
        --changed-course) changed="$2" ;; --useful) useful="$2" ;; --note) note="$2" ;; --actor) actor="$2" ;;
        *) die "unknown option: $1" ;;
      esac
      shift 2
    done
    bool_ok --changed-course "$changed"; bool_ok --useful "$useful"
    [ -n "$note" ] || die "--note is required (what the advice did, in one line)"
    append_decision '{id:$id, at:$at, actor:$actor, event:"advice.rated",
                      value:{thread:$th, reply_to:$re, changed_course:$c, useful:$u, note:$n}}' \
      --arg th "$th" --arg re "$re" --argjson c "$changed" --argjson u "$useful" --arg n "$note"
    ;;
  missed)
    th="${1:-}"; shift || true
    [ -n "$th" ] || die "usage: rate.sh missed <thread> --moment .. --what .."
    thread_ok "$th"
    moment="" what=""
    while [ $# -gt 0 ]; do
      [ $# -ge 2 ] || die "$1 needs a value"
      case "$1" in
        --moment) moment="$2" ;; --what) what="$2" ;; --actor) actor="$2" ;;
        *) die "unknown option: $1" ;;
      esac
      shift 2
    done
    moment_ok "$moment"
    [ -n "$what" ] || die "--what is required (what went wrong that the advisor would have caught)"
    append_decision '{id:$id, at:$at, actor:$actor, event:"advisor.missed",
                      value:{thread:$th, moment:$m, what_went_wrong:$w}}' \
      --arg th "$th" --arg m "$moment" --arg w "$what"
    ;;
  *) echo "usage: rate.sh rated <thread> <reply_to> ... | rate.sh missed <thread> ..." >&2; exit 2 ;;
esac
