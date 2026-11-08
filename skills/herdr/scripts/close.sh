#!/usr/bin/env bash
# close.sh - close a space, tab or pane YOU opened (ends the terminals in it). Refuses without --yes.
# Usage: close.sh --yes [-n] [--json] space|tab|pane ID
# ID comes from ls.sh. It refuses ids that contain this terminal, and ids not shown in the window.
# Never close what you did not open: the person's other work lives in the same window.
# Exit: 0 ok; 1 not found/failed; 2 usage, no --yes, or it would close the caller; 5 end log failed.
# -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 2 ] || hl_usage_err "want KIND ID"
if [ "$YES" != 1 ]; then hl_usage_err "refusing without --yes (closing ends the terminals inside)"; fi
case $1 in
  space|tab) cmd="$1.close"; obj=$(hl_obj "id=$2" confirmed:=true);;
  pane) cmd=pane.close; obj=$(hl_obj "pane=$2");;
  *) hl_usage_err "KIND is space, tab or pane";;
esac
hl_need herdr-app jq
me=$(hl_where 2>/dev/null || echo '{}')
if jq -e --arg k "$1" --arg i "$2" '.[$k] == $i' <<<"$me" >/dev/null 2>&1; then hl_die 2 "$2 contains this terminal; not closing it"; fi
close_it() {
  hl_exists "$1" "$2" || { echo "$SCRIPT: $1 $2 is not in the window" >&2; return 1; }
  hl_app_do "$3" "$4"
}
HL_DRYTXT=$(hl_show hl_app_do "$cmd" "$obj")
hl_op "$1:$2" - close_it "$1" "$2" "$cmd" "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
