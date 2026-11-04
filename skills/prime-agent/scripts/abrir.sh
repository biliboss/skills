#!/bin/sh
# abrir.sh <tema> [modelo]: abre o Prime Agent num pane à direita deste (sem tirar o foco), em $PRIME_LAB/<tema>.
#   modelo: padrão glm-5.3 (o mais potente para análise); glm-5.3-flash para tarefa curta.
#   Imprime o id do pane. Precisa de HERDR_PANE_ID (rode de dentro do herdr).
# Não lê stdin.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "abrir: falta o arquivo $CASA" >&2; exit 1; }
. "$CASA"
[ $# -ge 1 ] || { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
tema=$1
modelo=${2:-glm-5.3}
LAB="${PRIME_LAB:-$HOME/src/prime-agent-lab}"
[ -n "${HERDR_PANE_ID:-}" ] || { echo "abrir: falta HERDR_PANE_ID (rode de dentro do herdr)" >&2; exit 1; }
dir="$LAB/$tema"
mkdir -p "$dir"
RODAR="$(cd "$(dirname "$0")" && pwd)/rodar.sh"
pane=$(herdr pane split "$HERDR_PANE_ID" --direction right --cwd "$dir" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
[ -n "$pane" ] && [ "$pane" != null ] || { echo "abrir: o herdr não devolveu o pane" >&2; exit 1; }
herdr pane run "$pane" "PA_MODEL=$modelo sh $RODAR" >/dev/null
herdr pane rename "$pane" "$tema-prime" >/dev/null
echo "$pane"
