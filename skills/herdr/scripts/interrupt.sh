#!/usr/bin/env bash
# interrupt.sh - press the stop key in a terminal and report what happened (stops the turn, not the process).
# Usage: interrupt.sh [-n] [--json] [--timeout S] TERMINAL
# --timeout S: seconds to watch for an effect (hc default 10).
# stdout: one row outcome<TAB>key (--json: raw). Exit: 0 ok; 1 failed; 2 usage; 4 blocked; 5 end log failed.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
o=()
if [ "${1:-}" = "--timeout" ]; then [ $# -ge 3 ] || hl_usage_err "--timeout needs S and TERMINAL"; o=(--timeout "$2"); shift 2; fi
[ $# -eq 1 ] || hl_usage_err "want exactly one TERMINAL"
hl_need hc jq
hl_op "$1" - hl_hc interrupt --json "${o[@]}" "$1"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" = 1 ]; then exit 0; fi
if [ "$JSON" = 1 ]; then echo "$OUT"; else jq -r '[.outcome, .key] | @tsv' <<<"$OUT"; fi
exit $rc
