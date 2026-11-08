#!/usr/bin/env bash
# remote-exec.sh - run one program on a machine without a terminal and get exactly what it wrote (hc exec).
# Usage: remote-exec.sh [-n] [--json] --on MACHINE [--cwd DIR] [--timeout S] [--env K=V]... [--stdin] -- PROGRAM [ARG...]
# No shell: argv is run as given (use `sh -c` yourself). --stdin feeds this script's stdin to the program.
# Argv and env values are never logged, only prog and a length. stdout is the program's stdout, stderr its stderr.
# Exit: 0 program exited 0; 1 failed or non-zero (code on stderr); 2 usage; 3 timed out; 5 end log failed.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need hc jq
on=; opts=(); in=
while [ $# -gt 0 ]; do
  case $1 in
    --on|--cwd|--timeout|--env) [ $# -ge 2 ] || hl_usage_err "$1 needs a value" ;;
  esac
  case $1 in
    --on) on=$2; opts+=(--on "$2"); shift 2;;
    --cwd|--timeout|--env) opts+=("$1" "$2"); shift 2;;
    --stdin) opts+=(-i); in=/dev/stdin; shift;;
    --) shift; break;;
    *) hl_usage_err "unknown option $1";;
  esac
done
[ -n "$on" ] && [ $# -ge 1 ] || hl_usage_err "--on MACHINE and a PROGRAM after -- are required"
tlen=0; for a in "$@"; do tlen=$((tlen + ${#a})); done
run_it() {
  local o c; o=$(hc exec --json "$@") || true; printf '%s\n' "$o"
  c=$(jq -r 'if .timed_out then 3 elif .code == 0 then 0 else 1 end' <<<"$o" 2>/dev/null); return "${c:-1}"
}
HL_EXTRA=(prog="$1" on="$on"); HL_IN=$in
HL_DRYTXT=$(hl_show hc exec --json "${opts[@]}" -- "$@")
hl_op "$on" "$tlen" run_it "${opts[@]}" -- "$@"; rc=$?
if [ "$DRY" = 1 ]; then exit 0; fi
if [ "$JSON" = 1 ]; then echo "$OUT"; else
  jq -r '.stdout' <<<"$OUT" 2>/dev/null; jq -r '.stderr' <<<"$OUT" >&2 2>/dev/null
fi
if [ $rc -eq 1 ]; then echo "$SCRIPT: program exit code $(jq -r '.code // "none (signal)"' <<<"$OUT" 2>/dev/null)" >&2; fi
exit $rc
