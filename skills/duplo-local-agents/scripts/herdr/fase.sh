#!/bin/sh
# SOMENTE HERDR: usa workspaces, abas e mover panes do herdr (herdr workspace|tab|pane move); não há equivalente no mux.sh.
# fase.sh: a mesa do herdr por fases. Cada fase é um workspace; cada item é uma aba; os panes da aba andam juntos.
#   montar              cria os workspaces que faltam, na ordem das fases (focus, backlog, working, ready to review, done today)
#   estado              mostra as fases, os itens e o estado de cada pane
#   mover <tab> <fase>  leva a aba inteira (o grupo) para a fase, numa aba nova com o mesmo nome
#   focar <tab>         focus vazio: monta os 4 panes fixos. Focus montado: TROCA (sem pane novo): o agente da frente vai para
#                       working (trabalha sozinho) ou backlog (com ficha), o novo entra embaixo do card, a aba é renomeada,
#                       grava o KV (focus-set --current X --pick-next) e roda o focus-check. Layout: .wiki/herdr-focus.md (card 70% e
#                       agente 30% à esquerda; title-bar e o Bili, MESA_BILI/H00, à direita)
#   concluir <tab>      fecha os agentes do item (imprime o id para retomar) e deixa só o cartão no done today
# <tab> é o tab_id (w5R:t2D) ou o nome da aba. As fases mudam com MESA_FASES (separadas por "|").
# O Bili (MESA_BILI, padrão H00) mora no focus: vai de um item ao próximo e nunca é fechado pelo concluir.
# Não lê stdin. Anda pelo terminal_id: o pane_id muda quando o pane troca de workspace, e o rótulo do pane se perde.
set -eu
AQUI="$(cd "$(dirname "$0")" && pwd)"
AGENTE="$AQUI/../agente.sh"
FASES="${MESA_FASES:-focus|backlog|working|ready to review|done today}"
CWD="${MESA_CWD:-$HOME}"
BILI="${MESA_BILI:-H00}"
uso() { sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso
cmd=$1; shift

ws_de()   { herdr workspace list | jq -r --arg l "$1" '.result.workspaces[] | select(.label==$l) | .workspace_id' | head -1; }
tab_de()  { case "$1" in *:t*) echo "$1" ;; *) herdr tab list | jq -r --arg l "$1" '[.result.tabs[] | select(.label==$l) | .tab_id][0] // empty' ;; esac; }
rotulo_tab() { herdr tab list | jq -r --arg t "$1" '.result.tabs[] | select(.tab_id==$t) | .label'; }
# os panes da aba, da esquerda para a direita: terminal_id, rótulo
panes_tab() { herdr pane list | jq -r --arg t "$1" '[.result.panes[] | select(.tab_id==$t)] | .[] | [.terminal_id, (.label // .terminal_title_stripped // "")] | @tsv'; }
bili_term() { herdr pane list | jq -r --arg b "$BILI - " '[.result.panes[] | select(((.label // "") | startswith($b)) or ((.terminal_title_stripped // "") | test("\\b(Bili|Hermes)\\b")))][0] | select(.) | [.terminal_id, .label] | @tsv'; }
pane_card() { herdr pane list | jq -r --arg t "$1" '[.result.panes[] | select(.tab_id==$t and .label=="card") | .pane_id][0] // empty'; }
pane_de_term() { herdr pane list | jq -r --arg t "$1" '.result.panes[] | select(.terminal_id==$t) | .pane_id'; }
tab_de_pane()  { herdr pane list | jq -r --arg p "$1" '.result.panes[] | select(.pane_id==$p) | .tab_id'; }
novo_tab() {  # <workspace> <rótulo> -> pane_id do pane novo
  herdr tab create --workspace "$1" --label "$2" --cwd "$CWD" | jq -r '[.. | .pane_id? // empty][0]'
}
# O card e a title-bar vêm das receitas do justfile do dev/prime-bili. Com o justfile no checkout do main, usa-o; enquanto o
# ramo run/prime-bili não entra, o justfile mora na worktree ~/biliboss.wt-prime-bili (TODO: tirar o desvio quando entrar).
JUST="$HOME/biliboss/dev/prime-bili/justfile"; [ -f "$JUST" ] || JUST="$HOME/biliboss.wt-prime-bili/dev/prime-bili/justfile"
JUST="${MESA_JUST:-$JUST}"
cartao_em() { herdr pane rename "$1" card >/dev/null; herdr pane run "$1" "clear; just -f '$JUST' card" >/dev/null; }
barra_em() { herdr pane rename "$1" title-bar >/dev/null; herdr pane run "$1" "clear; just -f '$JUST' title-bar" >/dev/null; }
# o id do Bili segue o rótulo do pane dele (o Hermes no título), mesmo quando o id muda
b0=$(bili_term | cut -f2 | grep -oE '^[HT][0-9]{2}' || true); [ -z "$b0" ] || BILI=$b0
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
    ft=$(herdr tab list | jq -r --arg w "$w" '[.result.tabs[] | select(.workspace_id==$w) | .tab_id][0] // empty')
    if [ -n "$ft" ] && [ "$ft" != "$t" ] && panes_tab "$ft" | grep -q '	card$' && panes_tab "$ft" | grep -q '	title-bar$'; then
      # TROCA: o focus já está montado (card, title-bar, o agente da frente, o Bili). Nenhum pane novo, nenhum reinício:
      # o card e a title-bar leem o KV mesa_focus.
      velho=$(rotulo_tab "$ft")
      frente=$(panes_tab "$ft" | grep -v '	card$' | grep -v '	title-bar$' | grep -v '	barra$' | grep -v "	$BILI - " || true)
      if [ -n "$frente" ]; then
        # trabalhando sozinho -> working; com ficha (desligado de propósito) -> backlog
        fase=working; [ ! -f "${BACKLOG_DIR:-$HOME/.local/state/herdr-backlog}/$velho.ficha" ] || fase=backlog
        printf '%s\n' "$frente" | leva "$(fase_ws "$fase")" "$velho" >/dev/null
      fi
      alvo=""
      panes_tab "$t" | while IFS='	' read -r term nome; do
        [ -n "$term" ] || continue
        if [ -z "$alvo" ]; then
          herdr pane move "$(pane_de_term "$term")" --tab "$ft" --split down --target-pane "$(pane_card "$ft")" --ratio 0.7 --no-focus >/dev/null
        else
          herdr pane move "$(pane_de_term "$term")" --tab "$ft" --split right --target-pane "$alvo" --ratio 0.5 --no-focus >/dev/null
        fi
        alvo=$(pane_de_term "$term"); [ -z "$nome" ] || herdr pane rename "$alvo" "$nome" >/dev/null
      done
      herdr tab rename "$ft" "$lab" >/dev/null
      nt=$ft
    else
      # MONTAGEM (o focus está vazio): 4 panes fixos. A barra nasce do menor tamanho que o herdr dá (ratio 0.1, cerca de
      # 6 linhas numa aba de 60); não tente menos.
      c=$(novo_tab "$w" "$lab"); cartao_em "$c"; nt=$(tab_de_pane "$c")
      br=$(herdr pane split "$c" --direction right --ratio 0.5 --no-focus | jq -r '[.. | .pane_id? // empty][0]')
      b=$(bili_term)
      if [ -n "$b" ]; then
        bt=${b%%"$(printf '\t')"*}; bl=${b#*"$(printf '\t')"}
        herdr pane move "$(pane_de_term "$bt")" --tab "$nt" --split down --target-pane "$br" --ratio 0.1 --no-focus >/dev/null
        herdr pane rename "$(pane_de_term "$bt")" "$bl" >/dev/null
      fi
      barra_em "$br"
      alvo=""
      panes_tab "$t" | grep -v '	card$' | grep -v '	title-bar$' | grep -v '	barra$' | grep -v "	$BILI - " | while IFS='	' read -r term nome; do
        [ -n "$term" ] || continue
        if [ -z "$alvo" ]; then
          herdr pane move "$(pane_de_term "$term")" --tab "$nt" --split down --target-pane "$c" --ratio 0.7 --no-focus >/dev/null
        else
          herdr pane move "$(pane_de_term "$term")" --tab "$nt" --split right --target-pane "$alvo" --ratio 0.5 --no-focus >/dev/null
        fi
        alvo=$(pane_de_term "$term"); [ -z "$nome" ] || herdr pane rename "$alvo" "$nome" >/dev/null
      done
      herdr pane list | jq -r --arg t "$t" '.result.panes[] | select(.tab_id==$t) | select(.label=="card" or .label=="title-bar" or .label=="barra") | .pane_id' |
        while read -r p; do herdr pane close "$p" >/dev/null; done
    fi
    # grava o KV que o card e a title-bar leem; --pick-next (o Bili escolhe o próximo) se o focus_set.py já o tem, senão --next
    if grep -q -- '--pick-next' "$(dirname "$JUST")/scripts/focus_set.py" 2>/dev/null; then
      just -f "$JUST" focus-set --current "$lab" --pick-next
    else
      prox=$(herdr tab list | jq -r --arg w "$(fase_ws 'ready to review')" '[.result.tabs[] | select(.workspace_id==$w) | .label][0] // empty')
      just -f "$JUST" focus-set --current "$lab" ${prox:+--next "$prox"}
    fi
    if just -f "$JUST" --summary 2>/dev/null | tr ' ' '\n' | grep -qx focus-check; then just -f "$JUST" focus-check || echo "fase.sh: aviso: o focus-check falhou" >&2; fi
    herdr tab focus "$nt" >/dev/null; echo "$nt" ;;

  concluir)
    [ $# -eq 1 ] || uso
    t=$(tab_de "$1"); [ -n "$t" ] || { echo "fase.sh: aba não achada: $1" >&2; exit 1; }
    w=$(fase_ws "done today"); lab=$(rotulo_tab "$t")
    [ -f "$HOME/.local/state/$lab.cartao.md" ] || echo "fase.sh: aviso: falta ~/.local/state/$lab.cartao.md; o cartão no done today só terá o objetivo" >&2
    herdr pane list | jq -r --arg t "$t" --arg b "$BILI - " '.result.panes[] | select(.tab_id==$t) | select((.label // "") != "card" and (.label // "") != "title-bar") | select((.label // "") | startswith($b) | not) | select(.agent != null) | .pane_id' |
      while read -r p; do sh "$AGENTE" fecha "$p"; done
    c=$(novo_tab "$w" "$lab"); cartao_em "$c"
    herdr pane list | jq -r --arg t "$t" --arg b "$BILI - " '.result.panes[] | select(.tab_id==$t) | select((.label // "") | startswith($b) | not) | .pane_id' | while read -r p; do herdr pane close "$p" >/dev/null; done
    herdr pane list | jq -e --arg t "$t" --arg b "$BILI - " '[.result.panes[] | select(.tab_id==$t) | select((.label // "") | startswith($b))] | length > 0' >/dev/null &&
      echo "fase.sh: aviso: o $BILI ficou sozinho na aba $lab; foque o próximo item antes de concluir, para ele ir junto" >&2
    echo "concluído: $lab (o cartão está no done today)" ;;

  *) uso ;;
esac
