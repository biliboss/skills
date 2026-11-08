#!/bin/sh
# check.sh [id]: uma linha por rodada, separada por tab: id, estado, segundos, branch, modelo.
# Rodada com meta.env ilegível aparece com `-` nos campos que não deu para ler; não derruba a listagem.
set -eu
. "$(dirname -- "$0")/lib.sh"

line() {
  dir="$1"
  id=$(basename -- "$dir")
  st=$(state_of "$dir" 2>/dev/null) || st=lost
  if fields=$(
    . "$dir/meta.env" 2>/dev/null || exit 1
    if [ -f "$dir/finished" ]; then end=$(cat "$dir/finished"); else end=$(date +%s); fi
    printf '%ss\t%s\t%s' "$((end - STARTED))" "$BRANCH" "$MODEL"
  ) 2>/dev/null; then
    printf '%s\t%s\t%s\n' "$id" "$st" "$fields"
  else
    printf '%s\t%s\t-\t-\t-\n' "$id" "$st"
  fi
}

if [ $# -gt 0 ]; then
  line "$(run_dir "$1")"
  exit 0
fi

[ -d "$DEVIN_RUNS_DIR" ] || exit 0
for d in "$DEVIN_RUNS_DIR"/*/; do
  [ -d "$d" ] || continue
  [ "$(basename -- "$d")" != batches ] || continue
  line "${d%/}" || true
done
