#!/usr/bin/env bash
# layout.sh - show the current layout name, or switch to a named layout or the next one.
# Usage: layout.sh [-n] [NAME | --next]
# With no argument it only prints the current layout (read-only). Layout files live in the app's home;
# see references/mods.md before editing any.
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -le 1 ] || hl_usage_err "at most one argument"
hl_need herdr-app jq
if [ $# -eq 0 ]; then herdr-app status | jq -r '.layout'; exit "${PIPESTATUS[0]}"; fi
obj='{}'
if [ "$1" != "--next" ]; then obj=$(hl_obj "name=$1"); fi
hl_op "$1" - hl_app_do layout.switch "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
