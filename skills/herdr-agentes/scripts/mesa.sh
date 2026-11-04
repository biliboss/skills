#!/bin/sh
# mesa.sh: arruma as sessões de agente do herdr pelo estado delas, em duas abas.
#   organizar   uma passada: quem está trabalhando vai para a aba "doing (N)" (lado a lado, N = o WIP);
#               quem parou (idle, done, blocked) vai para a aba "review (N)", para o dono revisar.
#   vigiar [s]  repete a passada a cada s segundos (padrão 15); rode em segundo plano.
# A aba do dono (a do pane de onde a mesa é ligada, $HERDR_PANE_ID, ou MESA_DONO=<pane>) é o foco e nunca se mexe,
# as abas que não têm agente ficam como estão, e nada fora do workspace do dono é tocado. Não lê stdin.
set -eu

TRAB="${MESA_ABA_TRABALHO:-doing}"
REV="${MESA_ABA_REVISAO:-review}"
DONO="${MESA_DONO:-${HERDR_PANE_ID:-}}"
[ -n "$DONO" ] || { echo "mesa: rode de dentro do herdr (HERDR_PANE_ID) ou passe MESA_DONO=<pane>" >&2; exit 1; }
# Só o workspace do dono: as sessões de outros workspaces nunca são tocadas.
WS="${MESA_WORKSPACE:-$(herdr pane list | jq -r --arg p "$DONO" '.result.panes[] | select(.pane_id == $p) | .workspace_id')}"
[ -n "$WS" ] || { echo "mesa: não achei o workspace do pane $DONO" >&2; exit 1; }
# A aba do dono é o foco: o que está nela (a sessão do dono e o que ele puxou para o lado) não se move.
FOCO=$(herdr pane list | jq -r --arg p "$DONO" '.result.panes[] | select(.pane_id == $p) | .tab_id')

uso() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

# A aba pelo nome base: "doing" acha "doing" e "doing (3)".
aba() { herdr tab list | jq -r --arg l "$1" --arg w "$WS" '[.result.tabs[] | select(.workspace_id == $w) | select(.label == $l or (.label | startswith($l + " ("))) | .tab_id][0] // empty'; }

# O nome da aba leva o WIP: "doing (N)", com N = os panes de agente nela.
contar() {
  for base in "$TRAB" "$REV"; do
    t=$(aba "$base"); [ -n "$t" ] || continue
    n=$(herdr pane list | jq -r --arg t "$t" '[.result.panes[] | select(.tab_id == $t and .agent)] | length')
    herdr tab rename "$t" "$base ($n)" >/dev/null
  done
}

# O último pane de uma aba, para encostar o próximo à direita dele.
ultimo() { herdr pane list | jq -r --arg t "$1" '[.result.panes[] | select(.tab_id == $t) | .pane_id] | last // empty'; }

mover() {
  pane=$1; destino=$2
  t=$(aba "$destino")
  if [ -z "$t" ]; then
    herdr pane move "$pane" --new-tab --workspace "$WS" --label "$destino" --no-focus >/dev/null
  else
    herdr pane move "$pane" --tab "$t" --split right --target-pane "$(ultimo "$t")" --no-focus >/dev/null
  fi
  echo "$(date +%H:%M:%S) $pane -> $destino"
}

organizar() {
  herdr pane list | jq -r --arg w "$WS" '.result.panes[] | select(.workspace_id == $w and .agent) | [.pane_id, .tab_id, .agent_status] | @tsv' |
  while IFS="$(printf '\t')" read -r pane tab estado; do
    [ "$pane" != "$DONO" ] && [ "$tab" != "$FOCO" ] || continue
    case "$estado" in
      working) destino=$TRAB ;;
      idle|done|blocked) destino=$REV ;;
      *) continue ;;
    esac
    [ "$tab" = "$(aba "$destino")" ] || mover "$pane" "$destino"
  done
  contar
}

[ $# -ge 1 ] || uso
case "$1" in
  organizar) organizar ;;
  vigiar)
    s=${2:-15}
    while :; do organizar || true; sleep "$s"; done ;;
  *) uso ;;
esac
