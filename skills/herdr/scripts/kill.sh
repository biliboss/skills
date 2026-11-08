#!/usr/bin/env bash
# kill.sh - end a terminal's program (hc kill: hangup, then escalate), optionally removing it. Refuses without --yes.
# Usage: kill.sh --yes [-n] [--json] [--rm] TERMINAL
# Only terminals you started: `hc ls` shows the person's other live work too. Refuses to kill the caller.
# --rm also removes the finished terminal (hc rm) once it is dead.
# Exit: 0 ok; 1 not found/failed; 2 usage, no --yes, or target is the caller; 5 end log failed.
# stdout: one row address, name, state, reason, removed (yes with --rm) (--json: raw hc output).
# -n prints the commands and does nothing. Never stops the app or the core: that is not this script.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
rm=0
if [ "${1:-}" = "--rm" ]; then rm=1; shift; fi
[ $# -eq 1 ] || hl_usage_err "want exactly one TERMINAL"
if [ "$YES" != 1 ]; then hl_usage_err "refusing without --yes (kill ends the program and its sub-agents)"; fi
hl_need hc jq
mine=; if [ -n "${HC_TERMINAL_ID:-}" ]; then mine=$(hc get "$HC_TERMINAL_ID" --json 2>/dev/null | jq -r '.name // empty'); fi
if [ -n "${HC_TERMINAL_ID:-}" ] && { [ "$1" = "$HC_TERMINAL_ID" ] || [ "$1" = "$mine" ]; }; then hl_die 2 "$1 is this terminal; not killing it"; fi
kill_it() { hl_hc kill --json "$1" || return $?; if [ "$2" = 1 ]; then hl_hc rm --json "$1"; fi; }
HL_DRYTXT=$(hl_show hc kill --json "$1"; if [ $rm = 1 ]; then hl_show hc rm --json "$1"; fi)
hl_op "$1" - kill_it "$1" "$rm"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then
  if [ "$JSON" = 1 ]; then printf '%s\n' "$OUT"; else
    jq -rs --arg rm "$rm" '.[0] | [.address, (.name // "-"), (.state // "-"), (.reason // "-"), (if $rm == "1" then "yes" else "no" end)] | @tsv' <<<"$OUT"
  fi
fi
exit $rc
