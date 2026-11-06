#!/bin/sh
# SOMENTE HERDR: usa workspaces, abas e mover panes do herdr (herdr workspace|tab|pane move); não há equivalente no mux.sh.
# backlog.sh: a aba "backlog (N)" do herdr, antes da "doing": uma sessão desligada por pane, numa grade igual
# (até 3 colunas), cada uma com um banner do que ela é, onde parou, o próximo passo e como retomar.
# Enter no pane retoma a sessão ali mesmo; ela vira agente trabalhando e a leva para a aba doing.
#   guardar <tema> claude|pi <id|arquivo.jsonl> "<o que é>" "<onde parou>" "<próximo passo>"
#                     guarda a ficha e remonta a aba
#   puxar <tema>      retoma a sessão à direita de quem chama (o foco), tira a ficha e remonta a aba
#   tirar <tema>      tira a ficha (a sessão não volta) e remonta a aba
#   arrumar           remonta a aba backlog em grade, a partir das fichas
#   mostrar <tema>    (roda no pane) o banner; Enter retoma
#   lista             as fichas guardadas
# As fichas ficam em ${BACKLOG_DIR:-~/.local/state/herdr-backlog}/<tema>.ficha. Não lê stdin, fora o Enter do mostrar.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "backlog: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_REPO_PRINCIPAL:?backlog: falta CASA_REPO_PRINCIPAL em $CASA}"
: "${CASA_CONTA_PRINCIPAL_NOME:?backlog: falta CASA_CONTA_PRINCIPAL_NOME em $CASA}"
: "${CASA_CONTA_PRINCIPAL_DIR:?backlog: falta CASA_CONTA_PRINCIPAL_DIR em $CASA}"

AQUI="$(cd "$(dirname "$0")" && pwd)"
PI_CLAUDE="$AQUI/../../../pi/scripts/pi-claude.sh"
DIR="${BACKLOG_DIR:-$HOME/.local/state/herdr-backlog}"
ABA="${MESA_ABA_BACKLOG:-backlog}"
TRAB="${MESA_ABA_TRABALHO:-doing}"
REV="${MESA_ABA_REVISAO:-review}"
# Só o workspace de quem chama (ou MESA_WORKSPACE): nada fora dele é tocado.
WS="${MESA_WORKSPACE:-$(herdr pane list | jq -r --arg p "${HERDR_PANE_ID:-}" '.result.panes[] | select(.pane_id == $p) | .workspace_id')}"
uso() { sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso
cmd=$1; shift

aba_de() { herdr tab list | jq -r --arg l "$1" --arg w "$WS" '[.result.tabs[] | select(.workspace_id == $w) | select(.label == $l or (.label | startswith($l + " ("))) | .tab_id][0] // empty'; }
panes_de() { herdr pane list | jq -r --arg t "$1" '.result.panes[] | select(.tab_id == $t) | .pane_id'; }
novo_pane() { herdr pane split "$1" --direction "$2" --ratio "$3" --cwd "$CASA_REPO_PRINCIPAL" --no-focus | jq -r '[.. | .pane_id? // empty][0]'; }
campo() { sed -n "s/^$1=//p" "$2"; }

# Leva uma aba para o fim da barra, sem parar os panes (o herdr não reordena abas).
para_o_fim() {
  t=$(aba_de "$1"); [ -n "$t" ] || return 0
  rotulo=$(herdr tab list | jq -r --arg t "$t" '.result.tabs[] | select(.tab_id == $t) | .label')
  nova=; ult=
  for p in $(panes_de "$t"); do
    if [ -z "$nova" ]; then
      herdr pane move "$p" --new-tab --workspace "$WS" --label "$rotulo" --no-focus >/dev/null
      nova=$(herdr pane list | jq -r --arg p "$p" '.result.panes[] | select(.pane_id == $p) | .tab_id')
    else
      herdr pane move "$p" --tab "$nova" --split right --target-pane "$ult" --no-focus >/dev/null
    fi
    ult=$p
  done
}

arrumar() {
  mkdir -p "$DIR"
  temas=$(for f in "$DIR"/*.ficha; do [ -f "$f" ] && campo tema "$f"; done)
  velha=$(aba_de "$ABA")
  [ -z "$velha" ] || herdr tab close "$velha" >/dev/null
  n=$(printf '%s\n' "$temas" | grep -c . || true)
  [ "$n" -gt 0 ] || return 0
  cols=3; [ "$n" -ge 3 ] || cols=$n
  linhas=$(( (n + cols - 1) / cols ))
  # As colunas: a primeira pane e mais cols-1 à direita, cada uma com a mesma largura.
  primeira=$(herdr tab create --workspace "$WS" --label "$ABA ($n)" --cwd "$CASA_REPO_PRINCIPAL" --no-focus | jq -r '.result.root_pane.pane_id')
  colunas="$primeira"; resto=$primeira; c=1
  while [ $c -lt $cols ]; do
    r=$(awk -v k=$((cols - c + 1)) 'BEGIN { printf "%.4f", 1 / k }')
    resto=$(novo_pane "$resto" right "$r"); colunas="$colunas $resto"; c=$((c + 1))
  done
  # Cada coluna em linhas iguais; a ordem dos panes é coluna a coluna, de cima para baixo.
  ordem=
  for col in $colunas; do
    ordem="$ordem $col"; resto=$col; l=1
    while [ $l -lt $linhas ]; do
      r=$(awk -v k=$((linhas - l + 1)) 'BEGIN { printf "%.4f", 1 / k }')
      resto=$(novo_pane "$resto" down "$r"); ordem="$ordem $resto"; l=$((l + 1))
    done
  done
  i=0
  for p in $ordem; do
    i=$((i + 1))
    tema=$(printf '%s\n' "$temas" | sed -n "${i}p")
    if [ -n "$tema" ]; then
      herdr pane run "$p" "sh $AQUI/backlog.sh mostrar $tema" >/dev/null
      herdr pane rename "$p" "$tema" >/dev/null
    else
      herdr pane close "$p" >/dev/null
    fi
  done
  # A backlog vem antes da doing e da review.
  para_o_fim "$TRAB"
  para_o_fim "$REV"
}

case "$cmd" in mostrar|lista) ;; *) [ -n "$WS" ] || { echo "backlog: rode de dentro do herdr (HERDR_PANE_ID) ou passe MESA_WORKSPACE" >&2; exit 1; } ;; esac

case "$cmd" in
  guardar)
    [ $# -eq 6 ] || uso
    case "$2" in claude|pi) ;; *) uso ;; esac
    mkdir -p "$DIR"
    printf 'tema=%s\nharness=%s\nid=%s\nquando=%s\noque=%s\nparou=%s\nproximo=%s\n' \
      "$1" "$2" "$3" "$(date '+%d/%m %H:%M')" "$4" "$5" "$6" > "$DIR/$1.ficha"
    arrumar
    ;;
  puxar)
    [ $# -eq 1 ] || uso
    f="$DIR/$1.ficha"; [ -f "$f" ] || { echo "backlog: sem ficha $f" >&2; exit 1; }
    [ -n "${HERDR_PANE_ID:-}" ] || { echo "backlog: puxar precisa de HERDR_PANE_ID (rode de dentro do herdr)" >&2; exit 1; }
    harness=$(campo harness "$f"); id=$(campo id "$f")
    pane=$(herdr pane split "$HERDR_PANE_ID" --direction right --cwd "$CASA_REPO_PRINCIPAL" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
    case "$harness" in
      claude) herdr pane run "$pane" "CLAUDE_CONFIG_DIR=$CASA_CONTA_PRINCIPAL_DIR claude --dangerously-skip-permissions --resume $id" >/dev/null ;;
      pi) herdr pane run "$pane" "sh $PI_CLAUDE $CASA_CONTA_PRINCIPAL_NOME --model claude-bridge/claude-opus-5-5 --thinking medium --session $id" >/dev/null ;;
    esac
    herdr pane rename "$pane" "$1" >/dev/null
    mkdir -p "$DIR/puxadas"; mv "$f" "$DIR/puxadas/"
    arrumar
    echo "$pane"
    ;;
  tirar)
    [ $# -eq 1 ] || uso
    rm -f "$DIR/$1.ficha"
    arrumar
    ;;
  arrumar) arrumar ;;
  mostrar)
    [ $# -eq 1 ] || uso
    f="$DIR/$1.ficha"; [ -f "$f" ] || { echo "backlog: sem ficha $f" >&2; exit 1; }
    harness=$(campo harness "$f"); id=$(campo id "$f")
    titulo=$(campo tema "$f" | tr '[:lower:]' '[:upper:]' | sed 's/./& /g')
    w=$(( $(tput cols 2>/dev/null || echo 74) - 6 )); [ "$w" -le 66 ] || w=66; [ "$w" -ge 30 ] || w=30
    linha=$(printf '%*s' "$w" '' | sed 's/ /═/g')
    secao() { printf '\n  \033[1m%s\033[0m\n' "$1"; printf '%s\n' "$2" | fold -s -w "$((w - 2))" | sed 's/^/    /'; }
    clear
    printf '\n  ╔%s╗\n  ║ %-*s║\n  ╚%s╝\n' "$linha" "$((w - 1))" "$titulo" "$linha"
    secao "O QUE É" "$(campo oque "$f")"
    secao "ONDE PAROU" "$(campo parou "$f")"
    secao "PRÓXIMO" "$(campo proximo "$f")"
    printf '\n  \033[2m%s · desligada em %s · %s\033[0m\n' "$harness" "$(campo quando "$f")" "$(basename "$id" .jsonl | cut -c1-36)"
    printf '\n  ⏎ Enter retoma aqui\n'
    read -r _
    case "$harness" in
      claude) exec env CLAUDE_CONFIG_DIR="$CASA_CONTA_PRINCIPAL_DIR" claude --dangerously-skip-permissions --resume "$id" ;;
      pi) exec sh "$PI_CLAUDE" "$CASA_CONTA_PRINCIPAL_NOME" --model claude-bridge/claude-opus-5-5 --thinking medium --session "$id" ;;
    esac
    ;;
  lista)
    for f in "$DIR"/*.ficha; do [ -f "$f" ] && printf '%s\t%s\t%s\n' "$(campo tema "$f")" "$(campo harness "$f")" "$(campo proximo "$f" | cut -c1-70)"; done
    ;;
  *) uso ;;
esac
