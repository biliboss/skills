#!/usr/bin/env bash
# wait.sh - wait for a terminal (stops working or exits), for text it prints, or for your children. Never sleep.
# Usage: wait.sh [--json] [--output TEXT] [--timeout S] [TERMINAL]
#        wait.sh [--json] --children any|all [--timeout S] [TERMINAL]
# stdout: TSV rows terminal reason status exit_code turn (one per child with --children). reason=message means a
#   message reached you (already in your input), not a result.
# Exit: 0 ended (a program that exited 0, or has no exit code); 1 error, not started, or a program that exited
#   non-zero (the code is in the exit_code column); 3 timed out (a check-in: the program still runs, wait again);
#   4 a waited terminal is blocked on a permission (read it, ask the person); 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need hc jq
o=()
while [ $# -gt 0 ]; do
  case $1 in
    --output|--children|--timeout) [ $# -ge 2 ] || hl_usage_err "$1 needs a value"; o+=("$1" "$2"); shift 2;;
    -*) hl_usage_err "unknown option $1";;
    *) break;;
  esac
done
[ $# -le 1 ] || hl_usage_err "at most one TERMINAL"
OUT=$(hl_hc wait --json "${o[@]}" "$@"); rc=$?
if ! jq -e . <<<"$OUT" >/dev/null 2>&1; then exit $rc; fi
if [ "$JSON" = 1 ]; then echo "$OUT"; else
  jq -r '([.] + (.children // []))[] | [.terminal // "-", .reason, (.status // "-"), (.exit_code // "-"), (.turn // "-")] | @tsv' <<<"$OUT"
fi
exit "$(hl_wait_rc "$OUT")"
