#!/bin/sh
# wait.sh <id> [--timeout <segundos>]: bloqueia até a rodada terminar e sai com o código do Devin.
# Sai com 124 no prazo e com 1 se o processo sumiu; 2 é erro de uso. Quem decide é o estado impresso na saída.
# Rode em background no harness, nunca em primeiro plano.
set -eu
. "$(dirname -- "$0")/lib.sh"

usage="uso: wait.sh <id> [--timeout <segundos>]"
[ $# -ge 1 ] || die "$usage" 2
id="$1"; shift
limit=0
if [ $# -gt 0 ]; then
  if [ "$1" != "--timeout" ] || [ $# -ne 2 ]; then die "$usage" 2; fi
  if ! printf '%s' "$2" | grep -qE '^[0-9]+$'; then die "--timeout pede um número de segundos, sem sinal: '$2'" 2; fi
  limit="$2"
fi
dir=$(run_dir "$id")
start=$(date +%s)

while :; do
  st=$(state_of "$dir")
  if [ "$st" != running ] && [ "$st" != starting ]; then break; fi
  if [ "$limit" -gt 0 ] && [ $(( $(date +%s) - start )) -ge "$limit" ]; then
    echo "devin: prazo esgotado esperando $id" >&2
    exit 124
  fi
  sleep 2
done

echo "$st"
if [ -f "$dir/exit" ]; then exit "$(cat "$dir/exit")"; fi
exit 1
