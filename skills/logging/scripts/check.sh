#!/usr/bin/env bash
# check.sh - verify logging works here: jq present, target file location writable,
# and an emit + read-back round trip in a temporary LOGGING_FILE.
# Usage: check.sh
# Env: LOGGING_FILE is only probed (never written); the round trip uses a temp dir.
# Exit: 0 all pass; 1 something failed; 2 usage.
set -u
case ${1:-} in -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0;; '') ;; *) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2;; esac
here=$(cd "$(dirname "$0")" && pwd)
fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1" >&2; fail=1; }

command -v jq >/dev/null 2>&1 && ok "jq present" || bad "jq not found"

file=${LOGGING_FILE:-$HOME/.local/state/logging/logs.jsonl}
if [ -e "$file" ]; then probe=$file; else
  probe=$(dirname "$file"); while [ ! -d "$probe" ] && [ "$probe" != "/" ]; do probe=$(dirname "$probe"); done
fi
if [ -w "$probe" ]; then ok "writable: $file"; else bad "not writable: $file (checked $probe)"; fi

tmp=$(mktemp -d "${TMPDIR:-/tmp}/logging-check.XXXXXX") || { bad "no temp dir"; exit 1; }
trap 'rm -rf "$tmp"' EXIT
export LOGGING_FILE="$tmp/logs.jsonl"
unset TRACEPARENT LOGGING_TRACE_ID
if "$here/emit.sh" check selftest n=1 name=x; then
  rec=$("$here/query.sh" --source check --event selftest --json 2>/dev/null)
  if printf '%s' "$rec" | jq -e '.Body == "check.selftest" and .Attributes.n == 1 and (.TraceId | test("^[0-9a-f]{32}$")) and (.SpanId | test("^[0-9a-f]{16}$")) and (.Timestamp | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}\\.[0-9]{3}Z$"))' >/dev/null 2>&1
  then ok "emit and read back"; else bad "read back mismatch: $rec"; fi
else bad "emit failed"; fi
[ $fail = 0 ] && echo "logging: pass" || echo "logging: fail" >&2
exit $fail
