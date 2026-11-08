#!/bin/sh
# _worker.sh <pasta da rodada>: uso interno do run.sh. Roda o Devin no worktree e grava a resposta e o código de saída.
set -u
. "$(dirname -- "$0")/lib.sh"

dir="$1"
. "$dir/meta.env"

cd "$WORKTREE" || { date +%s > "$dir/finished"; echo 1 > "$dir/exit"; exit 1; }

"$DEVIN_BIN" -p --model "$MODEL" --permission-mode "$MODE" --respect-workspace-trust false \
  -- "$(cat "$dir/prompt.md")" > "$dir/answer.txt" 2> "$dir/log.txt" < /dev/null
code=$?

date +%s > "$dir/finished"
# A saída é o último arquivo gravado: quem vê `exit` já encontra todo o resto.
echo "$code" > "$dir/exit.tmp"
mv "$dir/exit.tmp" "$dir/exit"
exit "$code"
