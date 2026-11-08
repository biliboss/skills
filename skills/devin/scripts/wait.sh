#!/bin/sh
# wait.sh <id> [--timeout <segundos>]: bloqueia até a rodada terminar e sai com o código do Devin.
# Sai com 124 no prazo e com 1 se o processo sumiu. Rode em background no harness, nunca em primeiro plano.
set -eu
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: wait.sh <id> [--timeout <segundos>]" 2
dir=$(run_dir "$1")
limit=0
if [ "${2:-}" = "--timeout" ]; then limit="${3:?}"; fi
start=$(date +%s)

while [ "$(state_of "$dir")" = running ]; do
  if [ "$limit" -gt 0 ] && [ $(( $(date +%s) - start )) -ge "$limit" ]; then
    echo "devin: prazo esgotado esperando $1" >&2
    exit 124
  fi
  sleep 2
done

state_of "$dir"
if [ -f "$dir/exit" ]; then exit "$(cat "$dir/exit")"; fi
exit 1
