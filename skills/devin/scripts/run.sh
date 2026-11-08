#!/bin/sh
# run.sh --repo <caminho> (--prompt-file <arquivo> | --stdin) [--name <slug>] [--model <m>] [--mode <permissão>] [--base <ref>]
# Cria um worktree num branch novo, dispara o Devin destacado e imprime só o id da rodada. Não bloqueia.
# O stdin só é lido com --stdin. Códigos de saída: 0 disparou, 1 erro, 2 uso.
set -eu
. "$(dirname -- "$0")/lib.sh"

repo="" prompt_file="" from_stdin=0 name="tarefa" base="HEAD"
model="$DEVIN_SKILL_MODEL" mode="$DEVIN_SKILL_MODE"
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="${2:?}"; shift 2 ;;
    --prompt-file) prompt_file="${2:?}"; shift 2 ;;
    --stdin) from_stdin=1; shift ;;
    --name) name="${2:?}"; shift 2 ;;
    --model) model="${2:?}"; shift 2 ;;
    --mode) mode="${2:?}"; shift 2 ;;
    --base) base="${2:?}"; shift 2 ;;
    *) die "opção desconhecida: $1" 2 ;;
  esac
done

[ -n "$repo" ] || die "falta --repo" 2
[ "$mode" != dangerous ] || die "o modo dangerous não é aceito por esta skill" 2
if [ -n "$prompt_file" ] && [ "$from_stdin" = 1 ]; then die "use --prompt-file ou --stdin, não os dois" 2; fi
if [ -z "$prompt_file" ] && [ "$from_stdin" = 0 ]; then die "falta --prompt-file ou --stdin" 2; fi
if [ -n "$prompt_file" ] && [ ! -f "$prompt_file" ]; then die "arquivo não encontrado: $prompt_file" 2; fi

command -v "$DEVIN_BIN" >/dev/null 2>&1 || die "Devin CLI não encontrado: $DEVIN_BIN"
top=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null) || die "não é um repositório git: $repo"
base_sha=$(git -C "$top" rev-parse --verify "$base^{commit}" 2>/dev/null) || die "base não encontrada: $base"

slug=$(printf '%s' "$name" | tr -c 'a-zA-Z0-9-' '-' | cut -c1-40)
id="$(date -u +%Y%m%d-%H%M%S)-$slug"
dir="$DEVIN_RUNS_DIR/$id"
branch="devin/$id"
mkdir -p "$DEVIN_RUNS_DIR"
mkdir "$dir" || die "rodada já existe: $id"

# Qualquer falha daqui até o lançamento do worker desfaz o que foi criado (worktree, branch e pasta).
armed=1 made_wt=0
cleanup() {
  [ "$armed" = 1 ] || return 0
  armed=0
  if [ "$made_wt" = 1 ]; then
    git -C "$top" worktree remove --force --force "$dir/wt" >/dev/null 2>&1 || true
    git -C "$top" worktree prune >/dev/null 2>&1 || true
    git -C "$top" branch -q -D "$branch" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

# Marca de largada: sem pid ainda, a rodada está em `starting`, não `lost`. Expira sozinha (START_GRACE).
date +%s > "$dir/starting"

if [ -n "$prompt_file" ]; then cp "$prompt_file" "$dir/prompt.md"; else cat > "$dir/prompt.md"; fi
[ -s "$dir/prompt.md" ] || die "pedido vazio"

q() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
{
  echo "REPO=$(q "$top")"
  echo "WORKTREE=$(q "$dir/wt")"
  echo "BRANCH=$(q "$branch")"
  echo "BASE=$(q "$base_sha")"
  echo "BASE_REF=$(q "$base")"
  echo "MODEL=$(q "$model")"
  echo "MODE=$(q "$mode")"
  echo "STARTED=$(date +%s)"
} > "$dir/meta.env"

made_wt=1
git -C "$top" worktree add -q -b "$branch" "$dir/wt" "$base_sha" >&2

# setsid desliga o Devin do grupo de processos de quem chamou: ele sobrevive ao fim do shell.
# O worker grava o próprio pid (e a hora de início) e tira a marca de largada.
nohup perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV or die' \
  sh "$SKILL_DIR/scripts/_worker.sh" "$dir" >/dev/null 2>&1 </dev/null &
armed=0

printf '%s\n' "$id"
