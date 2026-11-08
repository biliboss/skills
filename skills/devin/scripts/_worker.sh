#!/bin/sh
# _worker.sh <pasta da rodada>: uso interno do run.sh. Roda o Devin no worktree e grava a resposta e o código de saída.
# Líder de grupo (setsid). Mata o Devin em TERM/INT/HUP e grava `exit`, para um kill educado virar `failed`.
set -u
. "$(dirname -- "$0")/lib.sh"

dir="$1"

# finish <código>: a saída é o último arquivo gravado, de forma atômica: quem vê `exit` já encontra o resto.
finish() {
  date +%s > "$dir/finished"
  echo "$1" > "$dir/exit.tmp"
  mv "$dir/exit.tmp" "$dir/exit"
}

# Identidade primeiro (pid e hora de início), de forma atômica; depois a largada termina.
printf '%s\n%s\n' "$$" "$(ident_of $$)" > "$dir/pid.tmp"
mv "$dir/pid.tmp" "$dir/pid"
unlink "$dir/starting" 2>/dev/null || true

dpid=""
on_term() {
  trap '' TERM INT HUP
  if [ -n "$dpid" ]; then
    kill -TERM "$dpid" 2>/dev/null || true
    n=0
    while kill -0 "$dpid" 2>/dev/null && [ "$n" -lt 10 ]; do sleep 1; n=$((n + 1)); done
    kill -KILL "$dpid" 2>/dev/null || true
    wait "$dpid" 2>/dev/null || true
  fi
  finish 143
  exit 143
}
trap on_term TERM INT HUP

. "$dir/meta.env" || { echo "worker: meta.env ilegível" >> "$dir/log.txt"; finish 1; exit 1; }
cd "$WORKTREE" || { echo "worker: não entrei em $WORKTREE" >> "$dir/log.txt"; finish 1; exit 1; }

"$DEVIN_BIN" -p --model "$MODEL" --permission-mode "$MODE" --respect-workspace-trust false \
  --prompt-file "$dir/prompt.md" > "$dir/answer.txt" 2> "$dir/log.txt" < /dev/null &
dpid=$!
wait "$dpid"
code=$?

finish "$code"
exit "$code"
