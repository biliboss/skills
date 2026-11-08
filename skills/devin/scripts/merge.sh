#!/bin/sh
# merge.sh --into <worktree> --message-file <arquivo> <id>...
# Integra rodadas prontas, um id por vez, na ordem dada (a do grafo de cartões). Só integra: NUNCA faz push.
# Recusa antes de começar: --into sujo ou em detached HEAD, --into de outro repositório, id que não está done.
# Para cada id: re-confere o escopo contra allowed; commita o trabalho no branch devin/<id> (assunto "devin: <nome do cartão>",
# corpo = conteúdo do message-file, onde vão os trailers de atribuição; só commita se houver alteração); git merge --no-ff
# no --into; roda os gates (prek) no --into sobre os arquivos que entraram.
# Conflito: merge --abort, diz no stderr qual id conflitou, em quais arquivos, e quais ficaram na fila; exit 1.
# Gate reprovado: para a fila, deixa o merge no --into, diz isso no stderr; exit 1. Escopo violado: para a fila; exit 1.
# Stdout: uma linha por id integrado. Saída: 0 tudo integrado, 1 parou, 2 uso ou pré-condição.
set -eu
. "$(dirname -- "$0")/lib.sh"

into="" msg=""
ids=""
while [ $# -gt 0 ]; do
  case "$1" in
    --into) into="${2:?}"; shift 2 ;;
    --message-file) msg="${2:?}"; shift 2 ;;
    -*) die "opção desconhecida: $1" 2 ;;
    *) ids="$ids $1"; shift ;;
  esac
done
[ -n "$into" ] && [ -n "$msg" ] && [ -n "$ids" ] || die "uso: merge.sh --into <worktree> --message-file <arquivo> <id>..." 2
[ -s "$msg" ] || die "message-file ausente ou vazio: $msg" 2
git -C "$into" rev-parse --git-dir >/dev/null 2>&1 || die "--into não é um worktree git: $into" 2
git -C "$into" symbolic-ref -q HEAD >/dev/null || die "--into está em detached HEAD: $into" 2
[ -z "$(git -C "$into" status --porcelain)" ] || die "--into tem alterações não commitadas: $into" 2
into_common=$(git -C "$into" rev-parse --path-format=absolute --git-common-dir)
sh "$(dirname -- "$0")/_gates.sh" "$into" || exit 2

for id in $ids; do
  dir=$(run_dir "$id")
  . "$dir/meta.env"
  [ "$(state_of "$dir")" = done ] || die "$id não está done ($(state_of "$dir")): nada foi integrado" 2
  [ -f "$dir/allowed" ] || die "$id sem $dir/allowed: nada foi integrado" 2
  [ "$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)" = "$into_common" ] \
    || die "$id é de outro repositório ($REPO): nada foi integrado" 2
done

pending="$ids"
for id in $ids; do
  pending=${pending# "$id"}
  dir=$(run_dir "$id")
  . "$dir/meta.env"
  name=$(printf '%s' "$id" | sed 's/^[0-9]\{8\}-[0-9]\{6\}-//')

  changed=$(changed_files "$WORKTREE" "$BASE")
  if [ -z "$changed" ]; then die "$id não alterou nada; parei aqui. Fila restante:$pending" 1; fi
  outside=$(printf '%s\n' "$changed" | scope_violations "$dir/allowed")
  if [ -n "$outside" ]; then
    echo "devin: $id tem arquivos fora de allowed; parei aqui. Fila restante:$pending" >&2
    printf '%s\n' "$outside" | sed 's/^/  /' >&2
    exit 1
  fi

  if [ -n "$(git -C "$WORKTREE" status --porcelain)" ]; then
    git -C "$WORKTREE" add -A
    { printf 'devin: %s\n\n' "$name"; cat "$msg"; } > "$dir/commit-msg.tmp"
    git -C "$WORKTREE" commit -q --no-verify -F "$dir/commit-msg.tmp"
  fi

  if ! git -C "$into" merge --no-ff -q -m "Merge $BRANCH ($name)" "$BRANCH" >/dev/null 2>&1; then
    conflicts=$(git -C "$into" diff --name-only --diff-filter=U)
    git -C "$into" merge --abort >/dev/null 2>&1 || true
    echo "devin: conflito ao integrar $id; merge abortado, --into intacto." >&2
    printf '%s\n' "$conflicts" | sed 's/^/  conflito: /' >&2
    echo "devin: ficaram na fila:$pending" >&2
    exit 1
  fi

  entered=$(git -C "$into" -c core.quotepath=off diff --name-only --no-renames HEAD^1 HEAD)
  existing=$(printf '%s\n' "$entered" | while IFS= read -r f; do if [ -e "$into/$f" ]; then printf '%s\n' "$f"; fi; done)
  if [ -n "$existing" ]; then
    set +e
    gates_out=$(printf '%s\n' "$existing" | tr '\n' '\0' | xargs -0 sh "$(dirname -- "$0")/_gates.sh" "$into" 2>&1)
    g=$?
    set -e
    if [ "$g" -ne 0 ]; then
      echo "devin: os gates reprovaram depois de integrar $id; o merge ficou em $into." >&2
      printf '%s\n' "$gates_out" >&2
      echo "devin: ficaram na fila:$pending" >&2
      exit 1
    fi
  fi
  printf '%s\n' "$id"
done
