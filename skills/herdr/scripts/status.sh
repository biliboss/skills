#!/usr/bin/env bash
# status.sh - what the window shows now: layout, focus, zoom, overlays and file/mod errors.
# Usage: status.sh [--json]
# stdout: key<TAB>value rows, plus one "error" row per error (--json: the raw object).
# Exit: 0 ok; 1 the window did not answer, or it reports errors; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 0 ] || hl_usage_err "takes no arguments"
hl_need herdr-app jq
OUT=$(herdr-app status) || hl_die 1 "herdr-app status failed: is the window open?"
if [ "$JSON" = 1 ]; then
  echo "$OUT"
else
  jq -r '(to_entries[] | select(.value | type != "object" and type != "array") | [.key, (.value | tostring)] | @tsv),
         (.errors[]? | ["error", tostring] | @tsv)' <<<"$OUT"
fi
jq -e '(.errors | length) == 0' <<<"$OUT" >/dev/null
