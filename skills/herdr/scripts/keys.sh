#!/usr/bin/env bash
# keys.sh - press named keys in a terminal (enter, esc, up, down, tab, ctrl+c, alt+x, f5, a ...).
# Usage: keys.sh [-n] [--json] TERMINAL KEY...
# For a dialog that wants arrow keys (e.g. a trust prompt: `keys.sh NAME down enter`). Keys are not text:
# use send.sh for text. Only the number of keys is logged.
# stdout: turn status. Exit: 0 ok; 1 failed; 2 usage; 4 blocked on permission; 5 end log failed.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -ge 2 ] || hl_usage_err "want TERMINAL KEY..."
hl_need hc jq
t=$1; shift
HL_EXTRA=(keys=$#)
hl_op "$t" - hl_hc keys --json "$t" "$@"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" = 1 ]; then exit 0; fi
if [ "$JSON" = 1 ]; then echo "$OUT"; else jq -r '[.turn, (.status // "-")] | @tsv' <<<"$OUT"; fi
exit $rc
