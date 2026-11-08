#!/usr/bin/env bash
# rename.sh - rename a space or a tab (always give a useful name; an empty name is refused).
# Usage: rename.sh [-n] space|tab ID NAME
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
if [ $# -ne 3 ] || [ -z "$3" ]; then hl_usage_err "want KIND ID NAME"; fi
case $1 in space|tab) ;; *) hl_usage_err "KIND is space or tab";; esac
hl_need herdr-app jq
hl_op "$1:$2" "${#3}" hl_app_do "$1.rename" "$(hl_obj "id=$2" "name=$3")"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
