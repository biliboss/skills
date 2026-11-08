#!/usr/bin/env bash
# feedback.sh - draft a feedback report about Herdr for the person to review and send (nothing is sent by itself).
# Usage: feedback.sh [-n] TEXT|-
# Say what happened, what you expected, and the command you ran. Text from an argument or "-" for stdin.
# Only the text length is logged. Exit: 0 drafted; 1 failed; 2 usage; 5 end log failed. -n prints the command.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 1 ] || hl_usage_err "want TEXT or -"
hl_need herdr-app
text=$(hl_text "$1")
if [ -z "$text" ]; then hl_usage_err "empty feedback"; fi
hl_op feedback "${#text}" herdr-app feedback "$text"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then printf '%s\n' "$OUT"; fi
exit $rc
