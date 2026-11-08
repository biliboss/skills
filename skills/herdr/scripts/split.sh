#!/usr/bin/env bash
# split.sh - open a terminal beside the pane this script runs in (terminal.open, place right or down).
# Usage: split.sh [-n] [--json] [--pane ID] [--place right|down] [--folder DIR] [--argv JSON] [--name NAME]
# The split lands beside the FOCUSED pane, so if focus is elsewhere the caller's pane is focused first.
# --pane ID: split that pane instead (it must exist in `herdr-app ls`, else exit 1); it is focused first, the same flow.
# stdout: key<TAB>value of the ids created (--json: raw). Default place: right.
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints both commands and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need herdr-app jq
hl_kv "place folder argv name pane" "" "$@"
target=; keep=(); for kv in "${OBJARGS[@]}"; do case $kv in pane=*) target=${kv#pane=};; *) keep+=("$kv");; esac; done
OBJARGS=("${keep[@]}")
case " ${OBJARGS[*]} " in *" place="*) ;; *) OBJARGS+=("place=right");; esac
obj=$(hl_obj "${OBJARGS[@]}") || exit 1
case $(jq -r .place <<<"$obj") in right|down) ;; *) hl_usage_err "--place is right or down";; esac
focused=$(herdr-app status 2>/dev/null | jq -r '.focused_pane // empty')
if [ -n "$target" ]; then
  hl_exists pane "$target" || hl_die 1 "pane $target is not in the window (see ls.sh)"
  mine=$target
else
  mine=$(hl_where 2>/dev/null | jq -r '.pane // empty')
  if [ -z "$mine" ] || [ "$mine" = "$focused" ]; then mine=; fi
fi
split_beside() {
  if [ -n "$1" ]; then hl_app_do pane.focus "$(hl_obj pane="$1")" >/dev/null || return 1; fi
  hl_app_do terminal.open "$2"
}
HL_DRYTXT=$(hl_show hl_app_do terminal.open "$obj")
if [ -n "$mine" ]; then HL_DRYTXT=$(hl_show hl_app_do pane.focus "$(hl_obj pane="$mine")"; echo "$HL_DRYTXT"); fi
hl_op "${mine:-focused}" - split_beside "$mine" "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
