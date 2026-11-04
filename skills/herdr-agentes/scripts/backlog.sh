#!/bin/sh
# backlog.sh: a aba "backlog (N)" do herdr, antes da "doing": uma sessão desligada por pane, com um banner
# que explica o que ela fazia e como retomá-la. Enter no pane retoma a sessão ali mesmo; aí ela vira agente
# trabalhando, e o mesa.sh a leva para a doing.
#   guardar <tema> claude|pi <id|arquivo.jsonl> <resumo...>   guarda a ficha e põe o pane na aba backlog
#   mostrar <tema>                                            (roda no pane) o banner; Enter retoma
#   lista                                                     as fichas guardadas
# As fichas ficam em ${BACKLOG_DIR:-~/.local/state/herdr-backlog}/<tema>.ficha. Não lê stdin, fora o Enter do mostrar.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "backlog: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_REPO_PRINCIPAL:?backlog: falta CASA_REPO_PRINCIPAL em $CASA}"
: "${CASA_CONTA_PRINCIPAL_NOME:?backlog: falta CASA_CONTA_PRINCIPAL_NOME em $CASA}"
: "${CASA_CONTA_PRINCIPAL_DIR:?backlog: falta CASA_CONTA_PRINCIPAL_DIR em $CASA}"

AQUI="$(cd "$(dirname "$0")" && pwd)"
PI_CLAUDE="$AQUI/../../pi/scripts/pi-claude.sh"
DIR="${BACKLOG_DIR:-$HOME/.local/state/herdr-backlog}"
ABA="${MESA_ABA_BACKLOG:-backlog}"
TRAB="${MESA_ABA_TRABALHO:-doing}"
uso() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso
cmd=$1; shift

tabs() { herdr tab list | jq -r '.result.tabs[] | [.tab_id, .label] | @tsv'; }
aba_de() { herdr tab list | jq -r --arg l "$1" '[.result.tabs[] | select(.label == $l or (.label | startswith($l + " ("))) | .tab_id][0] // empty'; }

# A aba backlog vem antes da doing. O herdr não reordena abas: se a doing já existe, a backlog nasce
# e a doing é refeita depois dela (os panes da doing mudam de aba sem parar).
aba_backlog() {
  b=$(aba_de "$ABA")
  if [ -z "$b" ]; then
    b=$(herdr tab create --label "$ABA" --cwd "$CASA_REPO_PRINCIPAL" --no-focus | jq -r '.result.tab.tab_id')
    vazio=$(herdr pane list | jq -r --arg t "$b" '[.result.panes[] | select(.tab_id == $t) | .pane_id][0]')
    echo "$vazio" > "$DIR/.vazio"
    d=$(aba_de "$TRAB")
    if [ -n "$d" ]; then
      primeiro=1; nova=
      for p in $(herdr pane list | jq -r --arg t "$d" '.result.panes[] | select(.tab_id == $t) | .pane_id'); do
        if [ "$primeiro" = 1 ]; then
          herdr pane move "$p" --new-tab --label "$TRAB" --no-focus >/dev/null
          nova=$(herdr pane list | jq -r --arg p "$p" '.result.panes[] | select(.pane_id == $p) | .tab_id'); primeiro=0; ult=$p
        else
          herdr pane move "$p" --tab "$nova" --split right --target-pane "$ult" --no-focus >/dev/null; ult=$p
        fi
      done
    fi
  fi
  echo "$b"
}

case "$cmd" in
  guardar)
    [ $# -ge 4 ] || uso
    tema=$1; harness=$2; id=$3; shift 3
    case "$harness" in claude|pi) ;; *) uso ;; esac
    mkdir -p "$DIR"
    { printf 'tema=%s\nharness=%s\nid=%s\nquando=%s\n' "$tema" "$harness" "$id" "$(date '+%d/%m %H:%M')"; printf 'resumo=%s\n' "$*"; } > "$DIR/$tema.ficha"
    b=$(aba_backlog)
    vazio=$(cat "$DIR/.vazio" 2>/dev/null || true)
    if [ -n "$vazio" ] && herdr pane list | jq -e --arg p "$vazio" '.result.panes[] | select(.pane_id == $p)' >/dev/null; then
      pane=$vazio; rm -f "$DIR/.vazio"
    else
      ult=$(herdr pane list | jq -r --arg t "$b" '[.result.panes[] | select(.tab_id == $t) | .pane_id] | last')
      pane=$(herdr pane split "$ult" --direction down --cwd "$CASA_REPO_PRINCIPAL" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
    fi
    herdr pane run "$pane" "sh $AQUI/backlog.sh mostrar $tema" >/dev/null
    herdr pane rename "$pane" "$tema" >/dev/null
    n=$(herdr pane list | jq -r --arg t "$b" '[.result.panes[] | select(.tab_id == $t)] | length')
    herdr tab rename "$b" "$ABA ($n)" >/dev/null
    echo "$pane"
    ;;
  mostrar)
    [ $# -eq 1 ] || uso
    f="$DIR/$1.ficha"; [ -f "$f" ] || { echo "backlog: sem ficha $f" >&2; exit 1; }
    tema=$(sed -n 's/^tema=//p' "$f"); harness=$(sed -n 's/^harness=//p' "$f"); id=$(sed -n 's/^id=//p' "$f")
    quando=$(sed -n 's/^quando=//p' "$f"); resumo=$(sed -n 's/^resumo=//p' "$f")
    titulo=$(printf '%s' "$tema" | tr '[:lower:]' '[:upper:]' | sed 's/./& /g')
    clear
    printf '\n  ╔══════════════════════════════════════════════════════════╗\n'
    printf '  ║  %-56s║\n' "$titulo"
    printf '  ╚══════════════════════════════════════════════════════════╝\n\n'
    printf '%s\n' "$resumo" | fold -s -w 60 | sed 's/^/    /'
    printf '\n    harness: %s · desligada em %s\n    sessão:  %s\n\n' "$harness" "$quando" "$(basename "$id")"
    printf '    ⏎ Enter retoma aqui  ·  Ctrl-C deixa no backlog\n'
    read -r _
    case "$harness" in
      claude) exec env CLAUDE_CONFIG_DIR="$CASA_CONTA_PRINCIPAL_DIR" claude --dangerously-skip-permissions --resume "$id" ;;
      pi) exec sh "$PI_CLAUDE" "$CASA_CONTA_PRINCIPAL_NOME" --model claude-bridge/claude-opus-5-5 --thinking medium --session "$id" ;;
    esac
    ;;
  lista)
    for f in "$DIR"/*.ficha; do [ -f "$f" ] && printf '%s\t%s\t%s\n' "$(sed -n 's/^tema=//p' "$f")" "$(sed -n 's/^harness=//p' "$f")" "$(sed -n 's/^resumo=//p' "$f" | cut -c1-70)"; done
    ;;
  *) uso ;;
esac
