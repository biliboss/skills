#!/usr/bin/env bash
# whereami.sh - map this terminal ($HC_TERMINAL_ID, a terminal address, not a pane id) to its pane, tab and space.
# Usage: whereami.sh [--json]
# stdout: one TSV row: terminal pane tab tab_name space space_name status (--json: the raw object).
# Exit: 0 ok; 1 not inside an hc terminal, or not shown in the window; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 0 ] || hl_usage_err "takes no arguments"
hl_need herdr-app jq
w=$(hl_where) || exit 1
if [ "$JSON" = 1 ]; then echo "$w"; exit 0; fi
jq -r '[.terminal, .pane, .tab, .tab_name, .space, .space_name, .status] | map(. // "-") | @tsv' <<<"$w"
