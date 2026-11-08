#!/usr/bin/env bash
# zoom.sh - toggle zoom: show only one pane of its tab, or all panes again.
# Usage: zoom.sh [-n] [PANE]
# PANE is a pane id from ls.sh (default: the focused pane). Calling it again undoes the zoom.
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -le 1 ] || hl_usage_err "at most one PANE"
hl_need herdr-app jq
obj='{}'
if [ $# -eq 1 ]; then obj=$(hl_obj "pane=$1"); fi
hl_op "${1:-focused}" - hl_app_do pane.zoom "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
