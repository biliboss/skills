#!/usr/bin/env bash
# ls.sh - what the window shows (spaces > tabs > terminals), or with --core every live hc terminal.
# Usage: ls.sh [--core] [--json]
# stdout: TSV. Window: terminal pane status app name tab tab_name space space_name.
#         --core: address name status agent where. --json: the raw reply.
# Exit: 0 ok; 1 the window or core did not answer; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need herdr-app hc jq
if [ "${1:-}" = "--core" ]; then
  OUT=$(hl_hc ls --json) || exit $?
  if [ "$JSON" = 1 ]; then echo "$OUT"; exit 0; fi
  jq -r '.terminals[] | [.address, .name // "-", .status // "-", .agent // "-", .where // .cwd] | @tsv' <<<"$OUT"
  exit 0
fi
[ $# -eq 0 ] || hl_usage_err "unexpected '$1'"
OUT=$(herdr-app ls) || hl_die 1 "herdr-app ls failed: is the window open?"
if [ "$JSON" = 1 ]; then echo "$OUT"; exit 0; fi
jq -r '.spaces[] as $s | $s.tabs[] as $b | $b.terminals[]
  | [.terminal, .pane, .status, .app // "-", .name // "-", $b.id, $b.name // "-", $s.id, $s.name // "-"] | @tsv' <<<"$OUT"
