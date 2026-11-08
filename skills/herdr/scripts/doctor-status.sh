#!/usr/bin/env bash
# doctor-status.sh - is Herdr healthy? Versions, the window answering, its file/mod errors, the core answering,
# and any terminal blocked or in error. Read-only: it never starts, stops or restarts the app or the core.
# Usage: doctor-status.sh [--json]
# stdout: TSV check result detail (--json: an array of the same). result is ok, WARN or FAIL.
# Exit: 0 no FAIL; 1 at least one FAIL (WARN does not fail); 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 0 ] || hl_usage_err "takes no arguments"
hl_need herdr-app hc jq
rows=$(mktemp "${TMPDIR:-/tmp}/doctor.XXXXXX") || hl_die 1 "no temp file"
trap 'rm -f "$rows"' EXIT
row() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$rows"; }
row app-version ok "$(herdr-app --version 2>&1 | head -1)"
row core-version ok "$(hc -V 2>&1 | head -1)"
if st=$(herdr-app status 2>&1) && n=$(jq -r '.errors | length' <<<"$st" 2>/dev/null); then
  if [ "$n" = 0 ]; then row window ok "layout $(jq -r .layout <<<"$st")"; else row window FAIL "$n error(s): run status.sh"; fi
else row window FAIL "no answer: is the app open?"; fi
if ls=$(hc ls --json 2>&1) && b=$(jq -r '[.terminals[] | select(.status == "blocked" or .status == "error")] | length' <<<"$ls" 2>/dev/null); then
  row core ok "$(jq -r '.terminals | length' <<<"$ls") live terminals"
  if [ "$b" = 0 ]; then row attention ok none; else row attention WARN "$b blocked or in error: ls.sh --core"; fi
else row core FAIL "no answer from hc"; fi
if [ "$JSON" = 1 ]; then jq -R -s 'split("\n")[:-1] | map(split("\t") | {check: .[0], result: .[1], detail: .[2]})' "$rows"; else cat "$rows"; fi
! grep -q $'\tFAIL\t' "$rows"
