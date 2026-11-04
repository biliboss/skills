#!/bin/sh
# abrir.sh <tema|pasta> [modelo]: abre o Prime Agent num pane à direita deste (sem tirar o foco), em $PRIME_LAB/<tema> ou na pasta dada.
#   modelo: padrão glm-5.3 (o mais potente para análise); glm-5.3-flash para tarefa curta.
#   Imprime o id do pane. Funciona no herdr e no tmux (scripts/mux.sh); sem multiplexador, imprime o comando e sai com 3.
# Não lê stdin.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "abrir: falta o arquivo $CASA" >&2; exit 1; }
. "$CASA"
[ $# -ge 1 ] || { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
tema=$1
modelo=${2:-glm-5.3}
LAB="${PRIME_LAB:-$HOME/src/prime-agent-lab}"
# Um caminho (com barra) é a pasta da análise; um nome vai para $PRIME_LAB/<tema>.
case "$tema" in
  */*) dir=$tema ;;
  *) dir="$LAB/$tema" ;;
esac
mkdir -p "$dir"
AQUI="$(cd "$(dirname "$0")" && pwd)"
sh "$AQUI/mux.sh" abrir "$dir" "$(basename "$dir")-prime" "PA_MODEL=$modelo sh $AQUI/rodar.sh"
