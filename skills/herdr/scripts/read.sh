#!/usr/bin/env bash
# read.sh - print a terminal's screen and history (hc read). Read before you resend, and before you trust a launch.
# Usage: read.sh [--json] [--lines N] TERMINAL
# --lines N: history lines above the screen (default 0: only the visible screen). While a terminal is working,
#   blocked or in error only the screen comes back; the note "incomplete" on stderr says so.
# stdout: the text (--json: the raw reply). Exit: 0 ok; 1 not found/failed; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
n=0
if [ "${1:-}" = "--lines" ]; then [ $# -ge 3 ] || hl_usage_err "--lines needs N and TERMINAL"; n=$2; shift 2; fi
case $n in *[!0-9]*|'') hl_usage_err "--lines wants a number";; esac
[ $# -eq 1 ] || hl_usage_err "want exactly one TERMINAL"
hl_need hc jq
OUT=$(hl_hc read --json --lines "$n" "$1") || exit $?
jq -r 'select(.complete == false) | "read: incomplete (\(.why // "unknown")): only the screen" ' <<<"$OUT" >&2
if [ "$JSON" = 1 ]; then echo "$OUT"; else jq -r '.text' <<<"$OUT"; fi
