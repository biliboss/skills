#!/bin/sh
# gate.sh <id>: confere, por fora do Devin, o que a rodada alterou. Recusa rodada running.
# (a) escopo: os arquivos alterados no worktree contra a base (commits, staged, unstaged, não rastreados não ignorados)
#     têm de casar com $dir/allowed (caminho exato ou glob simples: * sem /, ** com /, ?); o que sobrar reprova, listado.
# (b) gates: prek, estágio pre-commit nos arquivos alterados e estágio pre-push; nunca modificam arquivo.
# Sem arquivo alterado, reprova (o cartão não fez nada). Grava tudo em $dir/gate.txt.
# Saída: 0 aprovado, 1 reprovado, 2 não pôde rodar (sem allowed, sem config de gates ou sem prek).
set -eu
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: gate.sh <id>" 2
dir=$(run_dir "$1")
. "$dir/meta.env"
[ "$(state_of "$dir")" != running ] || die "rodada ainda ativa: $1"
[ -d "$WORKTREE" ] || die "worktree não encontrado: $WORKTREE" 2
[ -f "$dir/allowed" ] || die "sem $dir/allowed: o escopo do cartão não foi gravado (batch.sh grava)" 2
sh "$(dirname -- "$0")/_gates.sh" "$WORKTREE" || exit $?

changed=$(changed_files "$WORKTREE" "$BASE")
out="$dir/gate.txt"
verdict=0
{
  if [ -z "$changed" ]; then
    echo "reprovado: nenhum arquivo alterado (o cartão não fez nada)"
    verdict=1
  else
    echo "== escopo"
    outside=$(printf '%s\n' "$changed" | scope_violations "$dir/allowed")
    if [ -n "$outside" ]; then
      echo "reprovado: arquivos fora de allowed:"
      printf '%s\n' "$outside" | sed 's/^/  /'
      verdict=1
    else
      echo "ok: $(printf '%s\n' "$changed" | wc -l | tr -d ' ') arquivo(s) dentro de allowed"
    fi
    # Arquivos apagados não vão aos gates.
    existing=$(printf '%s\n' "$changed" | while IFS= read -r f; do if [ -e "$WORKTREE/$f" ]; then printf '%s\n' "$f"; fi; done)
    if [ -z "$existing" ]; then
      echo "(só remoções: sem arquivo para os gates)"
    else
      set +e
      printf '%s\n' "$existing" | tr '\n' '\0' | xargs -0 sh "$(dirname -- "$0")/_gates.sh" "$WORKTREE"
      g=$?
      set -e
      if [ "$g" -ne 0 ]; then verdict=1; fi
    fi
  fi
  if [ "$verdict" = 0 ]; then echo "APROVADO"; else echo "REPROVADO"; fi
} > "$out" 2>&1 || true
cat "$out"
if tail -1 "$out" | grep -q '^APROVADO$'; then exit 0; fi
exit 1
