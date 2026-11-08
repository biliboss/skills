#!/bin/sh
# clean.sh <id> [--force]: remove o worktree, o branch e o estado da rodada.
# Recusa rodada ativa (running ou starting) sempre. Sem --force, recusa também trabalho não integrado
# (alterações, não rastreados e ignorados incluídos) e qualquer coisa que não consiga verificar.
# Com --force sempre termina: remove o que der e apaga a pasta.
set -eu
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: clean.sh <id> [--force]" 2
id="$1"
force=0
if [ "${2:-}" = "--force" ]; then force=1; elif [ $# -gt 1 ]; then die "uso: clean.sh <id> [--force]" 2; fi
if [ $# -gt 2 ]; then die "uso: clean.sh <id> [--force]" 2; fi
dir=$(run_dir "$id")

st=$(state_of "$dir")
if [ "$st" = running ] || [ "$st" = starting ]; then die "rodada ainda ativa ($st): $id"; fi

# Os únicos valores aceitos: derivados da pasta. meta.env adulterado não aponta para outro lugar.
want_wt="$dir/wt"
want_branch="devin/$id"
REPO="" WORKTREE="$want_wt" BRANCH="$want_branch"
have_meta=0
if [ -f "$dir/meta.env" ]; then
  if ( . "$dir/meta.env" ) >/dev/null 2>&1; then
    have_meta=1
    REPO="" WORKTREE="" BRANCH=""
    . "$dir/meta.env"
    [ "$WORKTREE" = "$want_wt" ] || die "meta.env aponta o worktree para '$WORKTREE', esperado '$want_wt'; recusado"
    [ "$BRANCH" = "$want_branch" ] || die "meta.env aponta o branch para '$BRANCH', esperado '$want_branch'; recusado"
  elif [ "$force" = 0 ]; then
    die "meta.env ilegível em $id; use --force para apagar a rodada"
  fi
fi
# Sem meta.env legível, o repositório sai do próprio worktree, se ele ainda existir.
if [ -z "$REPO" ] && [ -e "$want_wt/.git" ]; then
  common=$(git -C "$want_wt" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
  if [ -n "$common" ]; then REPO=$(dirname -- "$common"); fi
fi

if [ "$force" = 0 ]; then
  if [ -e "$WORKTREE" ]; then
    top=$(git -C "$WORKTREE" rev-parse --show-toplevel 2>/dev/null || true)
    [ "$top" = "$(CDPATH= cd -- "$WORKTREE" && pwd -P)" ] || die "o worktree não é um checkout git funcional; conserte ou use --force"
    if ! out=$(git -C "$WORKTREE" status --porcelain --ignored --untracked-files=all 2>/dev/null); then
      die "não consegui verificar o worktree (git status falhou); conserte ou use --force"
    fi
    [ -z "$out" ] || die "o worktree tem alterações, arquivos novos ou ignorados; integre ou use --force"
  fi
  if [ -n "$REPO" ]; then
    [ -d "$REPO" ] || die "o repositório $REPO sumiu; não dá para verificar o branch; use --force"
    if git -C "$REPO" rev-parse --verify -q "$BRANCH" >/dev/null 2>&1; then
      if [ "$have_meta" = 0 ]; then die "sem meta.env não sei a base de $BRANCH; use --force"; fi
      ahead=$(git -C "$REPO" rev-list --count "$BASE..$BRANCH" 2>/dev/null) || die "não consegui comparar $BRANCH com a base; use --force"
      if [ "$ahead" -gt 0 ]; then
        git -C "$REPO" merge-base --is-ancestor "$BRANCH" HEAD 2>/dev/null || die "$BRANCH tem $ahead commit(s) fora do HEAD; integre ou use --force"
      fi
    fi
  elif [ "$have_meta" = 1 ]; then
    die "meta.env sem REPO; use --force"
  fi
fi

# Daqui para a frente nada pode interromper: com --force sempre termina; sem ele, tudo já foi verificado.
if [ -n "$REPO" ] && [ -d "$REPO" ]; then
  if [ -e "$WORKTREE" ]; then git -C "$REPO" worktree remove --force --force "$WORKTREE" >/dev/null 2>&1 || true; fi
  git -C "$REPO" worktree prune >/dev/null 2>&1 || true
  if git -C "$REPO" rev-parse --verify -q "$BRANCH" >/dev/null 2>&1; then
    git -C "$REPO" branch -q -D "$BRANCH" >/dev/null 2>&1 || true
  fi
fi
if [ -e "$WORKTREE" ] && [ "$WORKTREE" = "$want_wt" ]; then rm -rf -- "$want_wt"; fi
rm -rf -- "$dir"
echo "limpo: $id"
