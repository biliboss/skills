#!/usr/bin/env bash
# One line per decision point, whether the advisor was called or not (advisor.decided in decisions.jsonl).
#   decide.sh <thread> --moment plano|travou|terminou|irreversivel|ambiguidade --called true|false --reason "..." --task-kind <kind> [--actor <name>]
# task-kind is a short slug for the kind of work (skill, dev-console, debug, pesquisa, refactor...): `decisions.sh recent
# <task-kind>` reads these lines back before the next decision. Skipping is a decision too; record it with its reason.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

th="${1:-}"; shift || true
[ -n "$th" ] || die "usage: decide.sh <thread> --moment .. --called true|false --reason .. --task-kind .."
thread_ok "$th"
moment="" called="" reason="" kind=""
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || die "$1 needs a value"
  case "$1" in
    --moment) moment="$2" ;; --called) called="$2" ;; --reason) reason="$2" ;; --task-kind) kind="$2" ;; --actor) actor="$2" ;;
    *) die "unknown option: $1" ;;
  esac
  shift 2
done
moment_ok "$moment"; bool_ok --called "$called"
[ -n "$reason" ] || die "--reason is required (why call, or why skip)"
thread_ok "$kind"

append_decision '{id:$id, at:$at, actor:$actor, event:"advisor.decided",
                  value:{thread:$th, moment:$m, called:$called, reason:$r, task_kind:$k}}' \
  --arg th "$th" --arg m "$moment" --argjson called "$called" --arg r "$reason" --arg k "$kind"
