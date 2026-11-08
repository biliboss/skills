#!/usr/bin/env bash
# tail.sh - show the last records of the log file as raw JSON lines.
# Usage: tail.sh [-n N] [-f]      (N default 20; -f follows new records)
# Env: LOGGING_FILE (default $HOME/.local/state/logging/logs.jsonl)
# Exit: 0 ok; 1 file missing; 2 usage.
set -u
usage() { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; }
n=20; follow=0
while [ $# -gt 0 ]; do
  case $1 in
    -h|--help) usage; exit 0;;
    -n) [ $# -ge 2 ] || { usage >&2; exit 2; }; n=$2; shift 2;;
    -f) follow=1; shift;;
    *) usage >&2; exit 2;;
  esac
done
case $n in ''|*[!0-9]*) echo "tail: -n needs a number" >&2; exit 2;; esac
file=${LOGGING_FILE:-$HOME/.local/state/logging/logs.jsonl}
[ -f "$file" ] || { echo "tail: no log file at $file" >&2; exit 1; }
if [ $follow = 1 ]; then exec tail -n "$n" -f "$file"; else exec tail -n "$n" "$file"; fi
