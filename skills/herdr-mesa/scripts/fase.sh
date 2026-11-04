#!/bin/sh
# fase.sh: a mesa do herdr por fases. Cada fase é um workspace; cada item é uma aba; os panes da aba andam juntos.
#   montar              cria os workspaces que faltam, na ordem das fases (focus, backlog, working, ready to review, done today)
#   estado              mostra as fases, os itens e o estado de cada pane
#   mover <tab> <fase>  leva a aba inteira (o grupo) para a fase, numa aba nova com o mesmo nome
#   focar <tab>         leva o item para o focus: o cartão à esquerda, o agente à direita (o worker à direita dele)
#   concluir <tab>      fecha os agentes do item (imprime o id para retomar) e deixa só o cartão no done today
# <tab> é o tab_id (w5R:t2D) ou o nome da aba. As fases mudam com MESA_FASES (separadas por "|").
# Não lê stdin. Anda pelo terminal_id: o pane_id muda quando o pane troca de workspace, e o rótulo do pane se perde.
set -eu
AQUI="$(cd "$(dirname "$0")" && pwd)"
CARTAO="$AQUI/cartao.py"
AGENTE="$AQUI/../../herdr-agentes/scripts/agente.sh"
FASES="${MESA_FASES:-focus|backlog|working|ready to review|done today}"
CWD="${MESA_CWD:-$HOME}"
uso() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso
cmd=$1; shift

ws_de()   { herdr workspace list | jq -r --arg l "$1" '.result.workspaces[] | select(.label==$l) | .workspace_id' | head -1; }
tab_de()  { case "$1" in *:t*) echo "$1" ;; *) herdr tab list | jq -r --arg l "$1" '[.result.tabs[] | select(.label==$l) | .tab_id][0] // empty' ;; esac; }
rotulo_tab() { herdr tab list | jq -r --arg t "$1" '.result.tabs[] | select(.tab_id==$t) | .label'; }
# os panes da aba, da esquerda para a direita: terminal_id, rótulo
panes_tab() { herdr pane list | jq -r --arg t "$1" '[.result.panes[] | select(.tab_id==$t)] | .[] | [.terminal_id, (.label // .terminal_title_stripped // "")] | @tsv'; }
pane_de_term() { herdr pane list | jq -r --arg t "$1" '.result.panes[] | select(.terminal_id==$t) | .pane_id'; }
tab_de_pane()  { herdr pane list | jq -r --arg p "$1" '.result.panes[] | select(.pane_id==$p) | .tab_id'; }
novo_tab() {  # <workspace> <rótulo> -> pane_id do pane novo
  herdr tab create --workspace "$1" --label "$2" --cwd "$CWD" | jq -r '[.. | .pane_id? // empty][0]'
}
cartao_em() { herdr pane rename "$1" card >/dev/null; herdr pane run "$1" "clear; uv run -q '$CARTAO' 15" >/dev/null; }
fase_ws() { w=$(ws_de "$1"); [ -n "$w" ] || { echo "fase.sh: não há o workspace \"$1\"; rode: fase.sh montar" >&2; exit 1; }; echo "$w"; }

# Leva os panes (lista de terminal_id<TAB>rótulo) para uma aba nova no workspace, lado a lado; imprime o tab novo.
# Com $3 (pane alvo), o primeiro encaixa à direita dele em vez de abrir aba nova.
leva() {  # <workspace> <rótulo da aba> [pane alvo] <<< lista
  ws=$1; lab=$2; alvo=${3:-}; novo=""
  while IFS='	' read -r term nome; do
    [ -n "$term" ] || continue
    p=$(pane_de_term "$term")
    if [ -z "$alvo" ]; then
      herdr pane move "$p" --new-tab --workspace "$ws" --label "$lab" --no-focus >/dev/null
    else
      herdr pane move "$p" --tab "$(tab_de_pane "$alvo")" --split right --target-pane "$alvo" --ratio 0.5 --no-focus >/dev/null
    fi
    p=$(pane_de_term "$term"); [ -z "$nome" ] || herdr pane rename "$p" "$nome" >/dev/null
    alvo=$p; novo=$(tab_de_pane "$p")
  done
  echo "$novo"
}

case "$cmd" in
  montar)
    echo "$FASES" | tr '|' '\n' | while IFS= read -r f; do
      [ -n "$(ws_de "$f")" ] && continue
      herdr workspace create --label "$f" --cwd "$CWD" >/dev/null && echo "criado: $f"
    done
    herdr workspace list | jq -r '.result.workspaces[] | "\(.number). \(.label)"' ;;

  estado)
    ws=$(herdr workspace list); tabs=$(herdr tab list); panes=$(herdr pane list)
    echo "$ws" | jq -r '.result.workspaces[] | [.number, .workspace_id, .label] | @tsv' | while IFS='	' read -r n w l; do
      printf '%s. %s\n' "$n" "$l"
      echo "$tabs" | jq -r --arg w "$w" '.result.tabs[] | select(.workspace_id==$w) | [.tab_id, .label] | @tsv' | while IFS='	' read -r t tl; do
        printf '   %-24s %s\n' "$tl" "$(echo "$panes" | jq -r --arg t "$t" '[.result.panes[] | select(.tab_id==$t) | "\(.label // .terminal_title_stripped // "?"):\(.agent_status)"] | join("  ")')"
      done
    done ;;

  mover)
    [ $# -eq 2 ] || uso
    t=$(tab_de "$1"); [ -n "$t" ] || { echo "fase.sh: aba não achada: $1" >&2; exit 1; }
    w=$(fase_ws "$2"); lab=$(rotulo_tab "$t")
    panes_tab "$t" | leva "$w" "$lab" ;;

  focar)
    [ $# -eq 1 ] || uso
    t=$(tab_de "$1"); [ -n "$t" ] || { echo "fase.sh: aba não achada: $1" >&2; exit 1; }
    w=$(fase_ws focus); lab=$(rotulo_tab "$t")
    c=$(novo_tab "$w" "$lab"); cartao_em "$c"
    novo=$(panes_tab "$t" | grep -v '	card$' | leva "$w" "$lab" "$c")
    herdr tab focus "$novo" >/dev/null; echo "$novo" ;;

  concluir)
    [ $# -eq 1 ] || uso
    t=$(tab_de "$1"); [ -n "$t" ] || { echo "fase.sh: aba não achada: $1" >&2; exit 1; }
    w=$(fase_ws "done today"); lab=$(rotulo_tab "$t")
    [ -f "$HOME/.local/state/$lab.cartao.md" ] || echo "fase.sh: aviso: falta ~/.local/state/$lab.cartao.md; o cartão no done today só terá o objetivo" >&2
    herdr pane list | jq -r --arg t "$t" '.result.panes[] | select(.tab_id==$t) | select((.label // "") != "card") | select(.agent != null) | .pane_id' |
      while read -r p; do sh "$AGENTE" fecha "$p"; done
    c=$(novo_tab "$w" "$lab"); cartao_em "$c"
    herdr pane list | jq -r --arg t "$t" '.result.panes[] | select(.tab_id==$t) | .pane_id' | while read -r p; do herdr pane close "$p" >/dev/null; done
    echo "concluído: $lab (o cartão está no done today)" ;;

  *) uso ;;
esac
