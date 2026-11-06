#!/bin/sh
# SOMENTE HERDR: usa workspaces, abas e mover panes do herdr (herdr workspace|tab|pane move); não há equivalente no mux.sh.
# bili-trabalho.sh: o trabalho que uma sessão local passou ao Bili, acompanhado num pane da aba doing.
# A sessão local fecha (com a ficha para retomar); o pane mostra ao vivo as atividades da sessão de agente
# do Bili no cartão e o tempo desde o pedido e desde a última atividade. Quando o Bili responde no cartão,
# o pane vai para a aba review com o resumo e o ciclo; Enter retoma a sessão local para validar.
#   acompanhar <tema> <cartão> <desde> claude|pi <id|arquivo.jsonl> "<o que conferir na volta>"
#                       guarda a ficha e abre o pane na doing (o <desde> é o que o `linear-bili.sh pedir` imprime)
#   mostrar <tema>      (roda no pane) o painel ao vivo; no fim, o resumo e o Enter
# As fichas ficam em ${BACKLOG_DIR:-~/.local/state/herdr-backlog}/bili/<tema>.ficha. Não lê stdin, fora o Enter.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "bili-trabalho: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_REPO_PRINCIPAL:?bili-trabalho: falta CASA_REPO_PRINCIPAL em $CASA}"
: "${CASA_CONTA_PRINCIPAL_NOME:?bili-trabalho: falta CASA_CONTA_PRINCIPAL_NOME em $CASA}"
: "${CASA_CONTA_PRINCIPAL_DIR:?bili-trabalho: falta CASA_CONTA_PRINCIPAL_DIR em $CASA}"

AQUI="$(cd "$(dirname "$0")" && pwd)"
PI_CLAUDE="$AQUI/../../../pi/scripts/pi-claude.sh"
DONO="$AQUI/../../../linear/scripts/dono.sh"
DIR="${BACKLOG_DIR:-$HOME/.local/state/herdr-backlog}/bili"
TRAB="${MESA_ABA_TRABALHO:-doing}"
REV="${MESA_ABA_REVISAO:-review}"
PASSO="${BILI_TRABALHO_PASSO:-20}"
uso() { sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso
cmd=$1; shift

ws_de() { herdr pane list | jq -r --arg p "$1" '.result.panes[] | select(.pane_id == $p) | .workspace_id'; }
aba_de() { herdr tab list | jq -r --arg l "$1" --arg w "$2" '[.result.tabs[] | select(.workspace_id == $w) | select(.label == $l or (.label | startswith($l + " ("))) | .tab_id][0] // empty'; }
ultimo() { herdr pane list | jq -r --arg t "$1" '[.result.panes[] | select(.tab_id == $t) | .pane_id] | last // empty'; }
campo() { sed -n "s/^$1=//p" "$2"; }
segs() { date -j -u -f '%Y-%m-%dT%H:%M:%S' "$(printf '%s' "$1" | cut -c1-19)" +%s 2>/dev/null || echo 0; }
dur() { s=$1; [ "$s" -ge 3600 ] && printf '%dh%02dm' $((s / 3600)) $((s % 3600 / 60)) || printf '%dm%02ds' $((s / 60)) $((s % 60)); }

# Põe um pane na aba <rótulo> do workspace, à direita do último dela (ou numa aba nova).
para_aba() {
  pane=$1; rotulo=$2; ws=$(ws_de "$pane")
  t=$(aba_de "$rotulo" "$ws")
  if [ -z "$t" ]; then herdr pane move "$pane" --new-tab --workspace "$ws" --label "$rotulo" --no-focus >/dev/null
  else herdr pane move "$pane" --tab "$t" --split right --target-pane "$(ultimo "$t")" --no-focus >/dev/null; fi
}

case "$cmd" in
  acompanhar)
    [ $# -eq 6 ] || uso
    case "$4" in claude|pi) ;; *) uso ;; esac
    [ -n "${HERDR_PANE_ID:-}" ] || { echo "bili-trabalho: rode de dentro do herdr (HERDR_PANE_ID)" >&2; exit 1; }
    mkdir -p "$DIR"
    printf 'tema=%s\ncartao=%s\ndesde=%s\nharness=%s\nid=%s\nconferir=%s\n' "$1" "$2" "$3" "$4" "$5" "$6" > "$DIR/$1.ficha"
    ws=$(ws_de "$HERDR_PANE_ID"); t=$(aba_de "$TRAB" "$ws")
    if [ -z "$t" ]; then
      pane=$(herdr tab create --workspace "$ws" --label "$TRAB" --cwd "$CASA_REPO_PRINCIPAL" --no-focus | jq -r '.result.root_pane.pane_id')
    else
      pane=$(herdr pane split "$(ultimo "$t")" --direction right --cwd "$CASA_REPO_PRINCIPAL" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
    fi
    herdr pane run "$pane" "sh $AQUI/bili-trabalho.sh mostrar $1" >/dev/null
    herdr pane rename "$pane" "bili: $1" >/dev/null
    echo "$pane"
    ;;
  mostrar)
    [ $# -eq 1 ] || uso
    f="$DIR/$1.ficha"; [ -f "$f" ] || { echo "bili-trabalho: sem ficha $f" >&2; exit 1; }
    tema=$(campo tema "$f"); cartao=$(campo cartao "$f"); desde=$(campo desde "$f")
    t0=$(segs "$desde"); TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
    jq -n --arg id "$cartao" '{id:$id}' > "$TMP/c.json"
    resposta=
    while :; do
      sh "$DONO" 'query($id: String!) { issue(id: $id) { title comments(last: 15) { nodes { createdAt body user { name } agentSession { id } } } } }' "$TMP/c.json" > "$TMP/i.json" 2>/dev/null || true
      titulo=$(jq -r '.data.issue.title // ""' "$TMP/i.json")
      sessao=$(jq -r --arg d "$desde" '[.data.issue.comments.nodes[] | select(.agentSession != null and .createdAt >= ($d | .[0:19]))] | last | .agentSession.id // empty' "$TMP/i.json")
      resposta=$(jq -r --arg d "$desde" '[.data.issue.comments.nodes[] | select(.user.name == "Bili" and .createdAt > $d)] | first // empty | "\(.createdAt)\t\(.body)"' "$TMP/i.json")
      : > "$TMP/a.txt"; ult=$t0
      if [ -n "$sessao" ]; then
        jq -n --arg id "$sessao" '{id:$id}' > "$TMP/s.json"
        sh "$DONO" 'query($id: String!) { agentSession(id: $id) { status activities(last: 14) { nodes { createdAt content { __typename ... on AgentActivityThoughtContent { body } ... on AgentActivityActionContent { action parameter result } ... on AgentActivityResponseContent { body } ... on AgentActivityErrorContent { body } ... on AgentActivityElicitationContent { body } } } } } }' "$TMP/s.json" > "$TMP/s.out" 2>/dev/null || true
        jq -r '.data.agentSession.activities.nodes[]? | select(.content.__typename != "AgentActivityPromptContent") | "\(.createdAt)\t\(.content.__typename | sub("AgentActivity"; "") | sub("Content"; ""))\t\(.content.body // ((.content.action // "") + " " + (.content.parameter // "")))"' "$TMP/s.out" > "$TMP/a.txt"
        u=$(tail -1 "$TMP/a.txt" | cut -f1); [ -z "$u" ] || ult=$(segs "$u")
      fi
      agora=$(date +%s)
      clear
      printf '\n  \033[1m🤖 BILI · %s\033[0m  (%s)\n' "$tema" "$cartao"
      printf '  %s\n' "$titulo" | cut -c1-76
      printf '  pedido há %s · última atividade há %s\n\n' "$(dur $((agora - t0)))" "$(dur $((agora - ult)))"
      while IFS="$(printf '\t')" read -r quando tipo texto; do
        printf '  %s %-8s %s\n' "$(printf '%s' "$quando" | cut -c12-16)" "$tipo" "$(printf '%s' "$texto" | tr '\n' ' ' | cut -c1-60)"
      done < "$TMP/a.txt"
      [ -z "$resposta" ] || break
      sleep "$PASSO"
    done
    # O Bili respondeu: o resumo, a aba review e o Enter que retoma a sessão local.
    quando=$(printf '%s' "$resposta" | cut -f1); corpo=$(printf '%s' "$resposta" | cut -f2-)
    clear
    printf '\n  \033[1m✅ BILI RESPONDEU · %s\033[0m  (%s)\n' "$tema" "$cartao"
    printf '  ciclo: %s\n\n' "$(dur $(( $(segs "$quando") - t0 )))"
    printf '%s\n' "$corpo" | fold -s -w 74 | head -30 | sed 's/^/  /'
    printf '\n  \033[1mCONFERIR\033[0m\n'; printf '%s\n' "$(campo conferir "$f")" | fold -s -w 72 | sed 's/^/    /'
    printf '\n  ⏎ Enter retoma a sessão %s para validar\n' "$(campo harness "$f")"
    [ -z "${HERDR_PANE_ID:-}" ] || { para_aba "$HERDR_PANE_ID" "$REV"; herdr pane rename "$HERDR_PANE_ID" "$tema" >/dev/null; }
    read -r _
    id=$(campo id "$f"); mkdir -p "$DIR/feitas"; mv "$f" "$DIR/feitas/"
    case "$(campo harness "$DIR/feitas/$1.ficha")" in
      claude) exec env CLAUDE_CONFIG_DIR="$CASA_CONTA_PRINCIPAL_DIR" claude --dangerously-skip-permissions --resume "$id" ;;
      pi) exec sh "$PI_CLAUDE" "$CASA_CONTA_PRINCIPAL_NOME" --model claude-bridge/claude-opus-5-5 --thinking medium --session "$id" ;;
    esac
    ;;
  *) uso ;;
esac
