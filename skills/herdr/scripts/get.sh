#!/usr/bin/env bash
# get.sh - show one terminal: state, status, turn, exit code and whether its first message was sent.
# Usage: get.sh [--json] TERMINAL
# TERMINAL is an address (t7), a name, or machine/t7. If first_message_sent is false the launch task was NOT
# delivered: read.sh it, resolve readiness, then send (read before resending).
# stdout: address name state status turn exit_code first_message_sent cwd (--json: raw). Exit: 0 ok; 1 not found; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 1 ] || hl_usage_err "want exactly one TERMINAL"
hl_need hc jq
OUT=$(hl_hc get --json "$1") || exit $?
if [ "$JSON" = 1 ]; then echo "$OUT"; exit 0; fi
jq -r '[.address, .name // "-", .state, (.status | if type == "object" then .state else . end) // "-", .turn,
        .exit_code // "-", (.first_message | if . == null then "-" else (.sent | tostring) end), .cwd] | @tsv' <<<"$OUT"
