#!/usr/bin/env bash
# settle.sh - put a tab away on this screen (out of the lists, still running), or bring it back.
# Usage: settle.sh [-n] [--undo] [TAB_ID]
# TAB_ID defaults to the shown tab. The tab returns by itself when shown or when an agent in it needs the person.
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
cmd=tab.settle
if [ "${1:-}" = "--undo" ]; then cmd=tab.unsettle; shift; fi
[ $# -le 1 ] || hl_usage_err "at most one TAB_ID"
hl_need herdr-app jq
obj='{}'
if [ $# -eq 1 ]; then obj=$(hl_obj "id=$1"); fi
hl_op "${1:-shown}" - hl_app_do "$cmd" "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
