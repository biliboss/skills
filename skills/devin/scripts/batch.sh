#!/bin/sh
# batch.sh --repo <caminho> [--max N] [--args <json>] <script.mjs>
# Roda um script de orquestração (subconjunto da sintaxe de workflows do Claude: meta, args, phase, agent,
# parallel, pipeline) que dispara Devins por run.sh e wait.sh, sem gastar tokens do Claude enquanto esperam.
# Stdout: só o resultado final em JSON. Progresso em stderr. Estado em $DEVIN_RUNS_DIR/batches/<id>/.
# --max: Devins ao mesmo tempo, no script todo (padrão DEVIN_BATCH_MAX, 3). Saída: 0 ok, 1 etapa falhou, 2 uso.
# Rode sempre em background no harness.
set -eu
. "$(dirname -- "$0")/lib.sh"

command -v node >/dev/null 2>&1 || die "node não encontrado"
exec node "$SKILL_DIR/scripts/batch.mjs" "$@"
