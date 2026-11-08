#!/usr/bin/env bash
# do.sh - exit to the rest of the herdr-app catalog: list commands, or run one that has no dedicated script.
# Usage: do.sh --list [PATTERN]                       (read-only; PATTERN is a regex on the command name)
#        do.sh [-n] [--json] COMMAND [JSON_OBJECT | --key value ...]
# Values after --key that start with [ or { are sent as JSON, everything else as a string. Check the exact
# shape with --list first; every `do` command changes what the person sees. Argument values are never logged.
# stdout: key<TAB>value of the reply (--json: raw). {"error":...} goes to stderr.
# Exit: 0 ok; 1 failed; 2 usage; 5 end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need herdr-app jq
if [ "${1:-}" = "--list" ]; then
  herdr-app commands | jq -r --arg p "${2:-}" '.[] | select(.name | test($p))
    | [.name, (.args | map(.name + (if .required then "*" else "" end)) | join(",")), .about] | @tsv'
  exit 0
fi
[ $# -ge 1 ] || hl_usage_err "want COMMAND (see --list)"
cmd=$1; shift; obj='{}'; tlen=0
if [ $# -eq 1 ] && jq -e 'type == "object"' <<<"$1" >/dev/null 2>&1; then obj=$1; tlen=${#1}
else
  while [ $# -gt 0 ]; do
    case $1 in --?*) ;; *) hl_usage_err "expected --key value, got '$1'";; esac
    [ $# -ge 2 ] || hl_usage_err "$1 needs a value"
    tlen=$((tlen + ${#2}))
    case $2 in '['*|'{'*) obj=$(hl_obj "${1#--}:=$2");; *) obj=$(hl_obj "${1#--}=$2");; esac
    shift 2
  done
fi
HL_EXTRA=(command="$cmd")
hl_op "$cmd" "$tlen" hl_app_do "$cmd" "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
