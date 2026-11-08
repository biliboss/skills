#!/usr/bin/env bash
# machines.sh - list the other machines hc can reach (added with `hc machine add`, over ssh or a command).
# Usage: machines.sh [--json]
# stdout: TSV name target host version via session (--json: the raw reply). An empty list means none are added;
#   adding one changes the person's setup, so ask first (see references/remote.md).
# Exit: 0 ok; 1 hc did not answer; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 0 ] || hl_usage_err "takes no arguments"
hl_need hc jq
OUT=$(hl_hc machine ls --json) || exit $?
if [ "$JSON" = 1 ]; then echo "$OUT"; exit 0; fi
jq -r '.machines[] | [.name, .target, .host, .version, (.via | tostring), (.session // "-")] | @tsv' <<<"$OUT"
