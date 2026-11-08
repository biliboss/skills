#!/bin/sh
# review.sh <id>: a resposta do Devin, os commits, o diff contra a base e os arquivos novos.
# Falhou: acrescenta o fim do log. Para o diff inteiro: git -C <worktree> diff <base>.
# Sem meta.env ou sem git funcional no worktree, o relatório segue e marca o que faltou.
set -eu
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: review.sh <id>" 2
dir=$(run_dir "$1")
BRANCH="-" WORKTREE="$dir/wt" BASE=""
meta=ok
if [ -f "$dir/meta.env" ] && ( . "$dir/meta.env" ) >/dev/null 2>&1; then . "$dir/meta.env"; else meta=ausente; fi
state=$(state_of "$dir")

printf 'estado: %s\nbranch: %s\nworktree: %s\nbase: %s\n' "$state" "$BRANCH" "$WORKTREE" "${BASE:--}"
if [ "$meta" != ok ]; then echo "aviso: meta.env ausente ou ilegível"; fi
echo "== resposta"
if [ -f "$dir/answer.txt" ]; then cat "$dir/answer.txt"; fi
if [ -d "$WORKTREE" ]; then
  wtop=$(git -C "$WORKTREE" rev-parse --show-toplevel 2>/dev/null || true)
  if [ "$wtop" != "$(CDPATH= cd -- "$WORKTREE" && pwd -P)" ]; then
    echo "== git: o worktree não é um checkout funcional; commits e diff indisponíveis"
  elif [ -z "$BASE" ]; then
    echo "== git: base desconhecida (sem meta.env); commits e diff indisponíveis"
  else
    echo "== commits"
    git -C "$WORKTREE" log --oneline "$BASE..HEAD" 2>&1 || echo "(indisponível: git log falhou)"
    echo "== diff contra a base"
    git -C "$WORKTREE" diff --stat "$BASE" 2>&1 || echo "(indisponível: git diff falhou)"
  fi
  echo "== arquivos novos"
  git -C "$WORKTREE" ls-files --others --exclude-standard 2>&1 || echo "(indisponível: git ls-files falhou)"
fi
if [ "$state" != done ] && [ "$state" != running ] && [ -f "$dir/log.txt" ]; then
  echo "== log"
  tail -20 "$dir/log.txt"
fi
exit 0
