#!/usr/bin/env bash
# run.sh - run a slow or long-lived process (build, tests, server) in a named background hc terminal, not in your shell.
# Usage: run.sh [-n] [--json] --name NAME [--cwd DIR] [--on MACHINE] [--rm] [--wait | --ready TEXT] [--timeout S] -- CMD [ARG...]
# --wait: then wait for it to exit and return its wait result (a non-zero exit of the program makes this script exit 1;
#   the program's own code stays in the exit_code column); --ready TEXT: wait until it prints TEXT (a server is up).
# Without either it returns at once; use wait.sh and read.sh later. Argv is never logged, only prog and a length.
# stdout: address name state (plus wait.sh rows when waiting). Exit: 0 ok (with a wait: the program exited 0 or has no
#   exit code); 1 failed (or the waited program exited non-zero); 2 usage; 3 wait timed out (the process keeps
#   running: wait again); 4 blocked; 5 end log failed. The end log's exit_code is this result.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need hc jq
name=; opts=(); ready=; tmo=; mode=
while [ $# -gt 0 ]; do
  case $1 in
    --name|--cwd|--on|--ready|--timeout) [ $# -ge 2 ] || hl_usage_err "$1 needs a value" ;;
  esac
  case $1 in
    --name) name=$2; shift 2;;
    --cwd|--on) opts+=("$1" "$2"); shift 2;;
    --ready) mode=ready; ready=$2; shift 2;;
    --timeout) tmo=$2; shift 2;;
    --rm) opts+=(--rm); shift;;
    --wait) mode=wait; shift;;
    --) shift; break;;
    *) hl_usage_err "unknown option $1";;
  esac
done
[ $# -ge 1 ] || hl_usage_err "CMD is required after --"
hl_name "$name" || hl_usage_err "--name is required: 1-32 of a-z 0-9 - _"
tlen=0; for a in "$@"; do tlen=$((tlen + ${#a})); done
HL_EXTRA=(prog="$1")
wo=(); if [ -n "$ready" ]; then wo+=(--output "$ready"); fi; if [ -n "$tmo" ]; then wo+=(--timeout "$tmo"); fi
# run_it: hc run, then (with --wait/--ready) hc wait inside the logged operation, so the end log's exit_code is
# the script's result. Prints two compact JSON lines: the run result, then the wait result.
run_it() {
  local r w wrc
  r=$(hl_hc run --json --bg --no-notify --name "$name" "${opts[@]}" -- "$@") || return $?
  printf '%s\n' "$(jq -c . <<<"$r" 2>/dev/null || echo '{}')"
  [ -n "$mode" ] || return 0
  w=$(hl_hc wait --json "${wo[@]}" "$name"); wrc=$?
  if ! jq -e . <<<"$w" >/dev/null 2>&1; then return "$wrc"; fi
  printf '%s\n' "$(jq -c . <<<"$w")"
  return "$(hl_wait_rc "$w")"
}
HL_DRYTXT=$(hl_show hl_hc run --json --bg --no-notify --name "$name" "${opts[@]}" -- "$@"; if [ -n "$mode" ]; then hl_show hl_hc wait --json "${wo[@]}" "$name"; fi)
hl_op "$name" "$tlen" run_it "$@"; rc=$?
if [ "$DRY" = 1 ]; then exit 0; fi
run=$(sed -n 1p <<<"$OUT"); wres=$(sed -n 2p <<<"$OUT")
if [ -z "$run" ]; then exit $rc; fi
if [ "$JSON" = 1 ]; then echo "$run"; else jq -r '[.address, .name // "-", .state] | @tsv' <<<"$run"; fi
if [ -n "$wres" ]; then
  if [ "$JSON" = 1 ]; then echo "$wres"; else
    jq -r '([.] + (.children // []))[] | [.terminal // "-", .reason, (.status // "-"), (.exit_code // "-"), (.turn // "-")] | @tsv' <<<"$wres"
  fi
fi
exit $rc
