#!/usr/bin/env bash
# focus.sh - show something to the person: focus a pane, a terminal's pane, an agent, a tab or a space.
# Usage: focus.sh [-n] pane|terminal|agent|tab|space ID
# ID comes from ls.sh (pane id, terminal address, tab id, space id). Focus moves what the person sees.
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 2 ] || hl_usage_err "want KIND ID"
hl_need herdr-app jq
case $1 in
  pane) cmd=pane.focus; key=pane;;
  terminal) cmd=pane.focus; key=terminal;;
  agent) cmd=agent.focus; key=terminal;;
  tab) cmd=tab.select; key=id;;
  space) cmd=space.select; key=id;;
  *) hl_usage_err "unknown kind '$1'";;
esac
hl_op "$1:$2" - hl_app_do "$cmd" "$(hl_obj "$key=$2")"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
