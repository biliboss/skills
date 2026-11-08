#!/bin/sh
# check.sh [id]: uma linha por rodada, separada por tab: id, estado, segundos, branch, modelo.
set -eu
. "$(dirname -- "$0")/lib.sh"

line() {
  dir="$1"
  (
    . "$dir/meta.env"
    if [ -f "$dir/finished" ]; then end=$(cat "$dir/finished"); else end=$(date +%s); fi
    printf '%s\t%s\t%ss\t%s\t%s\n' "$(basename -- "$dir")" "$(state_of "$dir")" "$((end - STARTED))" "$BRANCH" "$MODEL"
  )
}

if [ $# -gt 0 ]; then
  line "$(run_dir "$1")"
  exit 0
fi

[ -d "$DEVIN_RUNS_DIR" ] || exit 0
for d in "$DEVIN_RUNS_DIR"/*/; do
  if [ -f "${d}meta.env" ]; then line "${d%/}"; fi
done
