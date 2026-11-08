#!/bin/sh
# review.sh <id>: a resposta do Devin, os commits, o diff contra a base e os arquivos novos.
# Falhou: acrescenta o fim do log. Para o diff inteiro: git -C <worktree> diff <base>.
set -eu
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: review.sh <id>" 2
dir=$(run_dir "$1")
. "$dir/meta.env"
state=$(state_of "$dir")

printf 'estado: %s\nbranch: %s\nworktree: %s\nbase: %s\n' "$state" "$BRANCH" "$WORKTREE" "$BASE"
echo "== resposta"
if [ -f "$dir/answer.txt" ]; then cat "$dir/answer.txt"; fi
if [ -d "$WORKTREE" ]; then
  echo "== commits"
  git -C "$WORKTREE" log --oneline "$BASE..HEAD"
  echo "== diff contra a base"
  git -C "$WORKTREE" diff --stat "$BASE"
  echo "== arquivos novos"
  git -C "$WORKTREE" ls-files --others --exclude-standard
fi
if [ "$state" != done ] && [ "$state" != running ] && [ -f "$dir/log.txt" ]; then
  echo "== log"
  tail -20 "$dir/log.txt"
fi
