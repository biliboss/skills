#!/usr/bin/env bash
# spawn.sh - start an agent (or a template) in a background hc terminal, with its FIRST TASK in the launch.
# Usage: spawn.sh [-n] [--json] --name NAME [--cwd DIR] [--on MACHINE] [--label K=V]... [--task TEXT|-] [--] PROGRAM|TEMPLATE [ARG...]
# Always `hc run --bg --name`. Put the task here (as ARG or --task): a send to a booting agent can be dropped.
# stdout: address name state status first_message_sent. A launch reply only means the terminal exists:
#   read it (read.sh) before trusting the program. Argv and task text are never logged, only prog and a length.
# Exit: 0 ok; 1 failed, or the first message was NOT sent (read before resending); 2 usage; 5 end log failed.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need hc jq
name=; task=; has_task=0; opts=()
while [ $# -gt 0 ]; do
  case $1 in
    --name|--cwd|--on|--label|--task) [ $# -ge 2 ] || hl_usage_err "$1 needs a value" ;;
  esac
  case $1 in
    --name) name=$2; shift 2;;
    --cwd|--on|--label) opts+=("$1" "$2"); shift 2;;
    --task) task=$(hl_text "$2"); has_task=1; shift 2;;
    --) shift; break;;
    -*) hl_usage_err "unknown option $1";;
    *) break;;
  esac
done
[ $# -ge 1 ] || hl_usage_err "PROGRAM or TEMPLATE is required"
hl_name "$name" || hl_usage_err "--name is required: 1-32 of a-z 0-9 - _"
prog=$1; shift; tlen=${#task}; for a in "$@"; do tlen=$((tlen + ${#a})); done
cmd=(hl_hc run --json --bg --name "$name" "${opts[@]}" -- "$prog" "$@")
if [ $has_task = 1 ]; then cmd+=("$task"); fi
HL_EXTRA=(prog="$prog")
hl_op "$name" "$tlen" "${cmd[@]}"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" = 1 ]; then exit 0; fi
if [ "$JSON" = 1 ]; then echo "$OUT"; else
  jq -r '[.address, .name // "-", .state, (.status.state // "-"), (.first_message | if . == null then "-" else (.sent | tostring) end)] | @tsv' <<<"$OUT"
fi
if jq -e '.first_message.sent == false' <<<"$OUT" >/dev/null 2>&1; then
  echo "$SCRIPT: the first message was NOT sent ($(jq -r '.first_message.reason // "no reason"' <<<"$OUT")); read.sh $name before resending" >&2; exit 1
fi
exit $rc
