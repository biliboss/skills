#!/usr/bin/env bash
# query.sh - filter log records. Default output is TSV: time, severity, source, body, trace, attributes.
# Usage: query.sh [--source S] [--event E] [--trace ID] [--since T] [-n N] [--all] [--json]
#   --event E  matches Body "E" or "<source>.E";  --since T: 90s, 15m, 2h, 1d or an ISO-8601 UTC time
#   -n N       keep only the last N matches;  --all also reads rotated files;  --json prints raw records
# Env: LOGGING_FILE (default $HOME/.local/state/logging/logs.jsonl)
# Exit: 0 ok (also with no match); 1 file missing or jq failed; 2 usage.
set -u
usage() { sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; }
src=""; ev=""; trace=""; since=""; n=""; all=0; json=0
while [ $# -gt 0 ]; do
  case $1 in
    -h|--help) usage; exit 0;;
    --source|--event|--trace|--since|-n) [ $# -ge 2 ] || { usage >&2; exit 2; }
      case $1 in --source) src=$2;; --event) ev=$2;; --trace) trace=$2;; --since) since=$2;; -n) n=$2;; esac
      shift 2;;
    --all) all=1; shift;;
    --json) json=1; shift;;
    *) usage >&2; exit 2;;
  esac
done
case $n in *[!0-9]*) echo "query: -n needs a number" >&2; exit 2;; esac
if [ -n "$since" ]; then
  case $since in [0-9]*[smhd]|[0-9][0-9][0-9][0-9]-*) ;; *) echo "query: bad --since '$since'" >&2; exit 2;; esac
fi
command -v jq >/dev/null 2>&1 || { echo "query: jq not found" >&2; exit 1; }
file=${LOGGING_FILE:-$HOME/.local/state/logging/logs.jsonl}
[ -f "$file" ] || { echo "query: no log file at $file" >&2; exit 1; }
files=""
if [ $all = 1 ]; then
  k=99; while [ $k -ge 1 ]; do [ -f "$file.$k" ] && files="$files $file.$k"; k=$((k-1)); done
fi
# Stage 1 filters (invalid lines skipped), optional tail, stage 2 formats.
# shellcheck disable=SC2086
cat $files "$file" | jq -R -c --arg src "$src" --arg ev "$ev" --arg trace "$trace" --arg since "$since" '
  def cutoff:
    if $since == "" then ""
    elif ($since | test("^[0-9]+[smhd]$")) then
      (now - (($since[:-1] | tonumber) * ({"s":1,"m":60,"h":3600,"d":86400}[$since[-1:]])))
      | floor | todate | rtrimstr("Z")
    else $since | rtrimstr("Z") end;
  cutoff as $c
  | (fromjson? | select(type == "object"))
  | select($src == "" or .Resource["service.name"] == $src)
  | select($ev == "" or .Body == $ev or (.Body | endswith("." + $ev)))
  | select($trace == "" or .TraceId == $trace)
  | select($c == "" or (.Timestamp >= $c))' \
  | { if [ -n "$n" ]; then tail -n "$n"; else cat; fi; } \
  | if [ $json = 1 ]; then cat; else
      jq -r '[.Timestamp, .SeverityText, .Resource["service.name"], .Body, .TraceId, (.Attributes | tojson)] | @tsv'
    fi
