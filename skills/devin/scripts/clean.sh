#!/bin/sh
# clean.sh <id> [--force]: remove o worktree, o branch e o estado da rodada.
# Recusa rodada ativa sempre. Sem --force, recusa também trabalho não integrado ao HEAD do repositório.
set -eu
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: clean.sh <id> [--force]" 2
dir=$(run_dir "$1")
force=0
if [ "${2:-}" = "--force" ]; then force=1; fi
. "$dir/meta.env"

[ "$(state_of "$dir")" != running ] || die "rodada ainda ativa: $1"

if [ "$force" = 0 ]; then
  if [ -d "$WORKTREE" ] && [ -n "$(git -C "$WORKTREE" status --porcelain)" ]; then
    die "o worktree tem alterações não commitadas; integre ou use --force"
  fi
  if git -C "$REPO" rev-parse --verify -q "$BRANCH" >/dev/null; then
    ahead=$(git -C "$REPO" rev-list --count "$BASE..$BRANCH")
    if [ "$ahead" -gt 0 ] && ! git -C "$REPO" merge-base --is-ancestor "$BRANCH" HEAD; then
      die "$BRANCH tem $ahead commit(s) fora do HEAD; integre ou use --force"
    fi
  fi
fi

if [ -d "$WORKTREE" ]; then git -C "$REPO" worktree remove --force "$WORKTREE"; fi
git -C "$REPO" worktree prune
if git -C "$REPO" rev-parse --verify -q "$BRANCH" >/dev/null; then git -C "$REPO" branch -q -D "$BRANCH"; fi
rm -rf -- "$dir"
echo "limpo: $1"
