#!/usr/bin/env bash
# emit.sh - append one OpenTelemetry-style log record (JSON line) to the log file.
# Usage: emit.sh [--severity LEVEL] <source> <event> [key=value ...]
#        emit.sh --trace-id          print a fresh 32-hex trace id and exit
# Record: Timestamp, SeverityText, Body="<source>.<event>", TraceId, SpanId,
#         Resource {"service.name": <source>}, Attributes {key: value}.
# Numeric-looking values (-12, 3.5; not 007) become JSON numbers.
# Env: LOGGING_FILE (default $HOME/.local/state/logging/logs.jsonl)
#      LOGGING_MAX_BYTES (default 10485760), LOGGING_KEEP rotated files (default 5)
#      LOGGING_TRACE_ID (32 hex, shared id) > TRACEPARENT (00-<trace>-<span>-<flags>) > generated
# Exit: 0 line durably appended; 1 failed (message on stderr); 2 usage.
set -u
usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' >&2; }
rand_hex() { od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; }
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then usage; exit 0; fi
if [ "${1:-}" = "--trace-id" ]; then rand_hex 16; echo; exit 0; fi

sev=INFO
if [ "${1:-}" = "--severity" ]; then
  [ $# -ge 2 ] || { usage; exit 2; }
  sev=$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]'); shift 2
fi
case $sev in TRACE|DEBUG|INFO|WARN|ERROR|FATAL) ;; *) echo "emit: bad severity '$sev'" >&2; exit 2;; esac
[ $# -ge 2 ] || { usage; exit 2; }
source=$1; event=$2; shift 2
case $source$event in *[[:space:]]*) echo "emit: source and event must not contain spaces" >&2; exit 2;; esac
[ -n "$source" ] && [ -n "$event" ] || { usage; exit 2; }
for kv in "$@"; do
  case $kv in [A-Za-z_]*=*) ;; *) echo "emit: bad attribute '$kv' (want key=value)" >&2; exit 2;; esac
done
command -v jq >/dev/null 2>&1 || { echo "emit: jq not found" >&2; exit 1; }

hex32='^[0-9a-f]{32}$'; tp='^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$'
trace=""
if [ -n "${LOGGING_TRACE_ID:-}" ]; then
  if [[ $LOGGING_TRACE_ID =~ $hex32 ]]; then trace=$LOGGING_TRACE_ID
  else echo "emit: ignoring invalid LOGGING_TRACE_ID" >&2; fi
fi
if [ -z "$trace" ] && [ -n "${TRACEPARENT:-}" ]; then
  if [[ $TRACEPARENT =~ $tp ]] && [ "${BASH_REMATCH[1]}" != 00000000000000000000000000000000 ]; then
    trace=${BASH_REMATCH[1]}
  else echo "emit: ignoring invalid TRACEPARENT" >&2; fi
fi
[ -n "$trace" ] || trace=$(rand_hex 16)
span=$(rand_hex 8)

line=$(jq -nc --arg sev "$sev" --arg src "$source" --arg ev "$event" --arg t "$trace" --arg s "$span" '
  ($ARGS.positional | map(index("=") as $i | {key: .[:$i], value: .[$i+1:]})
    | map(.value |= (if test("^-?(0|[1-9][0-9]{0,14})(\\.[0-9]{1,6})?$") then tonumber else . end))
    | from_entries) as $attrs
  | now as $n
  | {Timestamp: (($n|floor|todate|rtrimstr("Z")) + "." + ((($n*1000|floor) % 1000 | tostring) | ("000" + .)[-3:]) + "Z"),
     SeverityText: $sev, Body: ($src + "." + $ev), TraceId: $t, SpanId: $s,
     Resource: {"service.name": $src}, Attributes: $attrs}' --args "$@") \
  && [ -n "$line" ] || { echo "emit: could not build record" >&2; exit 1; }

file=${LOGGING_FILE:-$HOME/.local/state/logging/logs.jsonl}
max=${LOGGING_MAX_BYTES:-10485760}; keep=${LOGGING_KEEP:-5}
case $max$keep in *[!0-9]*) echo "emit: LOGGING_MAX_BYTES/LOGGING_KEEP must be integers" >&2; exit 2;; esac
mkdir -p "$(dirname "$file")" 2>/dev/null || { echo "emit: cannot create $(dirname "$file")" >&2; exit 1; }

# mkdir lock; a lock older than 10s (1 min if it has no owner stamp) is taken over by atomic rename.
lock="$file.lock"; got=0; i=0
if [ -e "$file" ] && [ ! -w "$file" ]; then echo "emit: $file is not writable" >&2; exit 1; fi
[ -w "$(dirname "$file")" ] || { echo "emit: $(dirname "$file") is not writable" >&2; exit 1; }
while [ $i -lt 400 ]; do
  if mkdir "$lock" 2>/dev/null; then got=1; echo "$$ $(date +%s)" > "$lock/owner" 2>/dev/null; break; fi
  ots=""; read -r _ ots 2>/dev/null < "$lock/owner"
  now=$(date +%s)
  if { [ -n "$ots" ] && [ $((now - ots)) -gt 10 ]; } || { [ -z "$ots" ] && [ -n "$(find "$lock" -maxdepth 0 -mmin +1 2>/dev/null)" ]; }; then
    mv "$lock" "$lock.stale.$$" 2>/dev/null && rm -rf "$lock.stale.$$"
  fi
  sleep 0.05; i=$((i + 1))
done
[ $got = 1 ] || { echo "emit: lock timeout on $lock" >&2; exit 1; }
trap 'rm -rf "$lock"' EXIT

if [ -f "$file" ] && [ "$(wc -c < "$file" | tr -d ' ')" -ge "$max" ]; then
  n=$keep
  while [ "$n" -gt 1 ]; do
    [ -f "$file.$((n-1))" ] && mv -f "$file.$((n-1))" "$file.$n"
    n=$((n-1))
  done
  if [ "$keep" -ge 1 ]; then mv -f "$file" "$file.1"; else : > "$file"; fi
fi
printf '%s\n' "$line" >> "$file" 2>/dev/null || { echo "emit: cannot append to $file" >&2; exit 1; }
