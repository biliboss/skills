#!/usr/bin/env bash
# remote-file.sh - read, write or edit a file on a machine (or here) with hc, instead of your local file tools.
# Usage: remote-file.sh read  [--on M] [--cwd DIR] [--offset N] [--limit N] PATH
#        remote-file.sh write [-n] [--on M] [--cwd DIR] PATH            (the content comes from stdin)
#        remote-file.sh edit  [-n] [--on M] [--cwd DIR] --old X --new Y [--old X2 --new Y2]... PATH
# Edit replaces text found exactly once, all pairs or none. Remote paths start at that machine's home unless --cwd.
# read is read-only (stdout: the text, --json: raw). write/edit are logged by length only, never content.
# Exit: 0 ok; 1 failed (edit_failed: add context to make the old text unique); 2 usage; 5 end log failed.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need hc jq
verb=${1:-}; shift
case $verb in read|write|edit) ;; *) hl_usage_err "first word is read, write or edit";; esac
opts=(); tlen=0
while [ $# -gt 1 ]; do
  case $1 in
    --on|--cwd) opts+=("$1" "$2");;
    --offset|--limit) [ "$verb" = read ] || hl_usage_err "$1 is for read"; opts+=("$1" "$2");;
    --old|--new) [ "$verb" = edit ] || hl_usage_err "$1 is for edit"; opts+=("$1" "$2"); tlen=$((tlen + ${#2}));;
    *) hl_usage_err "unknown option $1";;
  esac
  shift 2
done
[ $# -eq 1 ] || hl_usage_err "want exactly one PATH, last"
path=$1
if [ "$verb" = read ]; then
  OUT=$(hl_hc file read --json "${opts[@]}" "$path") || exit $?
  if [ "$JSON" = 1 ]; then echo "$OUT"; else jq -r '.text' <<<"$OUT"; fi
  exit 0
fi
if [ "$verb" = write ]; then
  tmp=$(mktemp "${TMPDIR:-/tmp}/remote-file.XXXXXX") || hl_die 1 "no temp file"
  trap 'rm -f "$tmp"' EXIT
  if [ "$DRY" != 1 ]; then cat > "$tmp"; fi
  tlen=$(wc -c < "$tmp" | tr -d ' '); HL_IN=$tmp
  HL_DRYTXT="$(hl_show hc file write --json "${opts[@]}" "$path") < (stdin)"
fi
hl_op "$path" "$tlen" hl_hc file "$verb" --json "${opts[@]}" "$path"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
