#!/usr/bin/env bash
# label.sh - set labels on a terminal (key=value; "key=" removes one). Labels such as herdr.space opt it into the window.
# Usage: label.sh [-n] [--json] TERMINAL KEY=VALUE...
# Only add labels the person asked for: unlabeled workers stay hidden on purpose. Label values are logged as a count.
# stdout: the labels now set, key<TAB>value rows (--json: raw hc output, the whole terminal record). Exit: 0 ok; 1 failed; 2 usage; 5 end log failed.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -ge 2 ] || hl_usage_err "want TERMINAL KEY=VALUE..."
t=$1; shift
for kv in "$@"; do case $kv in ?*=*) ;; *) hl_usage_err "bad label '$kv' (want key=value)";; esac; done
hl_need hc jq
HL_EXTRA=(labels=$#)
hl_op "$t" - hl_hc label --json "$t" "$@"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then
  if [ "$JSON" = 1 ]; then printf '%s\n' "$OUT"; else jq -r '.labels // {} | to_entries[] | [.key, (.value | if type == "string" then . else tojson end)] | @tsv' <<<"$OUT"; fi
fi
exit $rc
