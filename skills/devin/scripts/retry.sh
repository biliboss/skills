#!/bin/sh
# retry.sh <id> --prompt-file <arquivo> [--model <m>]
# Nova tentativa no mesmo worktree e no mesmo branch (sem criar branch): os cartões proíbem git e --base não levaria
# alteração sem commit. Recusa rodada running. Arquiva pedido, resposta, log, saída, fim e gate em $dir/attempts/<n>/,
# atualiza MODEL e STARTED do meta.env e dispara o Devin destacado, como o run.sh. Imprime o id.
# Modelo padrão: 1ª retentativa swe-2-medium, 2ª swe-2-max. A 3ª é recusada (exit 1), mesmo com --model: recorte o cartão.
# Saída: 0 disparou, 1 recusado ou erro, 2 uso.
set -eu
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: retry.sh <id> --prompt-file <arquivo> [--model <m>]" 2
id="$1"
shift
prompt_file="" model=""
while [ $# -gt 0 ]; do
  case "$1" in
    --prompt-file) prompt_file="${2:?}"; shift 2 ;;
    --model) model="${2:?}"; shift 2 ;;
    *) die "opção desconhecida: $1" 2 ;;
  esac
done
[ -n "$prompt_file" ] || die "falta --prompt-file" 2
[ -s "$prompt_file" ] || die "pedido ausente ou vazio: $prompt_file" 2

dir=$(run_dir "$id")
. "$dir/meta.env"
[ "$(state_of "$dir")" != running ] || die "rodada ainda ativa: $id"
[ -d "$WORKTREE" ] || die "worktree não encontrado: $WORKTREE"
command -v "$DEVIN_BIN" >/dev/null 2>&1 || die "Devin CLI não encontrado: $DEVIN_BIN"

done_n=0
if [ -d "$dir/attempts" ]; then done_n=$(find "$dir/attempts" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' '); fi
if [ "$done_n" -ge 2 ]; then die "$id já teve 2 retentativas: recorte o cartão em partes menores"; fi
if [ -z "$model" ]; then
  if [ "$done_n" = 0 ]; then model=swe-2-medium; else model=swe-2-max; fi
fi

arch="$dir/attempts/$((done_n + 1))"
mkdir -p "$arch"
for f in prompt.md answer.txt log.txt exit finished gate.txt; do
  if [ -f "$dir/$f" ]; then mv "$dir/$f" "$arch/$f"; fi
done
cp "$dir/meta.env" "$arch/meta.env"
rm -f "$dir/pid"
cp "$prompt_file" "$dir/prompt.md"

q() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
{
  grep -v -e '^MODEL=' -e '^STARTED=' "$dir/meta.env"
  echo "MODEL=$(q "$model")"
  echo "STARTED=$(date +%s)"
} > "$dir/meta.env.tmp"
mv "$dir/meta.env.tmp" "$dir/meta.env"

nohup perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV or die' \
  sh "$(dirname -- "$0")/_worker.sh" "$dir" >/dev/null 2>&1 </dev/null &
echo $! > "$dir/pid"

printf '%s\n' "$id"
