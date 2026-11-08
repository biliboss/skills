#!/usr/bin/env bash
# send.sh - paste text into a terminal and press Enter (hc send). Text from an argument, or "-" for stdin.
# Usage: send.sh [-n] [--json] [--force] [--if idle|working] [--wait] [--timeout S] TERMINAL TEXT|-
# Do not use it as the first task of a booting agent (spawn.sh does that); read.sh first, and never resend blind.
# --force types into a blocked terminal and may answer its permission dialog: only if the person said so.
# stdout: turn started status (with --wait: the wait result row). The text is never logged, only its length.
# Exit: 0 ok; 1 failed or not started; 2 usage; 3 wait timed out; 4 blocked on permission; 5 end log failed.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need hc jq
o=(); wait=0
while [ $# -gt 0 ]; do
  case $1 in
    --force) o+=(--force); shift;;
    --wait) o+=(--wait); wait=1; shift;;
    --if|--timeout) [ $# -ge 3 ] || hl_usage_err "$1 needs a value"; o+=("$1" "$2"); shift 2;;
    --) shift; break;;
    -*) hl_usage_err "unknown option $1";;
    *) break;;
  esac
done
[ $# -eq 2 ] || hl_usage_err "want TERMINAL TEXT|-"
text=$(hl_text "$2")
hl_op "$1" "${#text}" hl_hc send --json "${o[@]}" "$1" "$text"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" = 1 ]; then exit 0; fi
if [ "$JSON" = 1 ]; then echo "$OUT"; else jq -r '[.turn, (.started // "-"), (.status // "-")] | @tsv' <<<"$OUT"; fi
if [ $wait = 1 ]; then
  w=$(hl_wait_rc "$(jq -c '.wait // {}' <<<"$OUT")")
  if [ "$w" != 0 ]; then exit "$w"; fi
fi
exit $rc
