#!/bin/sh
# mux.sh: o pouco que se pede a um multiplexador, igual no herdr, no tmux ou sem nenhum.
#   qual                          diz qual multiplexador abre panes aqui: herdr, tmux ou nenhum
#   panes                         todos os panes dos dois, um por linha: id, mux, pane, nome, estado
#   abrir <pasta> <nome> <cmd>    abre um pane à direita deste, sem tirar o foco, roda <cmd>, dá o nome e imprime o id
#   ler <pane> [linhas]           as últimas linhas da tela do pane (padrão 80)
#   tecla <pane> <tecla>          manda uma tecla (Down, Enter, Escape, C-o)
#   manda <pane> <arquivo>        manda o texto do arquivo como uma mensagem e aperta Enter
#   nomear <pane> <nome> [ID]     dá o nome "ID - nome" ao pane (sem ID, o próximo livre do multiplexador dele)
# Cada pane tem um id de dois dígitos que diz o multiplexador: TNN no tmux (nas opções @tnn/@nome do pane,
# porque o Claude Code sobrescreve o título) e HNN no herdr (no rótulo do pane, "HNN - nome"). <pane> aceita
# o id (T01, H05) ou o id nativo (%4, w5R:p39). Para abrir vale $MUX, senão $HERDR_PANE_ID (herdr) ou $TMUX
# (tmux); sem nenhum, abrir imprime o comando para rodar num terminal à parte e sai com 3. Não lê stdin.
set -eu
uso() { sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso

tm() { command tmux "$@"; }
tem_tmux() { command -v tmux >/dev/null 2>&1 && tm list-panes -a >/dev/null 2>&1; }
tem_herdr() { command -v herdr >/dev/null 2>&1 && herdr pane list >/dev/null 2>&1; }
qual() {
  if [ -n "${MUX:-}" ]; then echo "$MUX"
  elif [ -n "${HERDR_PANE_ID:-}" ]; then echo herdr
  elif [ -n "${TMUX:-}" ]; then echo tmux
  else echo nenhum; fi
}
# os panes do herdr: pane_id<TAB>rótulo<TAB>estado
herdr_panes() { herdr pane list | jq -r '.result.panes[] | [.pane_id, (.label // ""), .agent_status] | @tsv'; }
# de quem é o pane: imprime "tmux %N" ou "herdr <pane_id>"
dono() {
  if printf '%s' "$1" | grep -qE '^T[0-9]{2}$'; then
    p=$(tm list-panes -a -F '#{pane_id} #{@tnn}' | awk -v t="$1" '$2==t {print $1; exit}')
    [ -n "$p" ] || { echo "mux: nenhum pane do tmux com o id $1" >&2; exit 1; }
    echo "tmux $p"
  elif printf '%s' "$1" | grep -qE '^H[0-9]{2}$'; then
    p=$(herdr_panes | awk -F'\t' -v t="$1" 'index($2, t" - ")==1 {print $1; exit}')
    [ -n "$p" ] || { echo "mux: nenhum pane do herdr com o id $1" >&2; exit 1; }
    echo "herdr $p"
  elif printf '%s' "$1" | grep -qE '^%[0-9]+$'; then echo "tmux $1"
  else echo "herdr $1"; fi
}
# os ids em uso, um por linha
ids() {
  if tem_tmux; then tm list-panes -a -F '#{@tnn}' | grep -E '^T[0-9]{2}$' || true; fi
  if tem_herdr; then herdr_panes | cut -f2 | grep -oE '^H[0-9]{2} - ' | cut -c1-3 || true; fi
}
# livre <T|H>: o próximo id livre daquele multiplexador
livre() {
  usados=$(ids); n=1
  while printf '%s\n' "$usados" | grep -qx "$(printf '%s%02d' "$1" $n)"; do n=$((n+1)); done
  printf '%s%02d' "$1" $n
}
# nomeia <tmux|herdr> <pane nativo> <nome> [ID]: grava o nome e imprime o id
nomeia() {
  if [ "$1" = tmux ]; then
    id=${4:-$(livre T)}
    tm set -p -t "$2" @tnn "$id"; tm set -p -t "$2" @nome "$3"
  else
    id=${4:-$(livre H)}
    herdr pane rename "$2" "$id - $3" >/dev/null
  fi
  echo "$id"
}
cmd=$1; shift

case "$cmd" in
  qual) qual ;;

  panes)
    if tem_tmux; then
      tm list-panes -a -F '#{@tnn}	tmux	#{pane_id}	#{@nome}	#{pane_current_command}' | awk -F'\t' 'BEGIN{OFS="\t"} {if($1=="")$1="-"; if($4=="")$4="-"; print}'
    fi
    if tem_herdr; then
      herdr_panes | awk -F'\t' 'BEGIN{OFS="\t"} {id="-"; nome=$2; if (match($2, /^H[0-9][0-9] - /)) {id=substr($2,1,3); nome=substr($2,7)} if(nome=="")nome="-"; print id, "herdr", $1, nome, $3}'
    fi ;;

  abrir)
    [ $# -eq 3 ] || uso
    dir=$1; nome=$2; run=$3; m=$(qual)
    if [ "$m" = herdr ]; then
      pane=$(herdr pane split "$HERDR_PANE_ID" --direction right --cwd "$dir" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
      [ -n "$pane" ] && [ "$pane" != null ] || { echo "mux: o herdr não devolveu o pane" >&2; exit 1; }
      herdr pane run "$pane" "$run" >/dev/null
      nomeia herdr "$pane" "$nome"
    elif [ "$m" = tmux ]; then
      # O comando vai por send-keys, não como argumento do split: assim o pane sobrevive se ele sair.
      pane=$(tm split-window -h -d -c "$dir" -P -F '#{pane_id}' ${TMUX_PANE:+-t "$TMUX_PANE"})
      tm send-keys -t "$pane" "$run" Enter
      nomeia tmux "$pane" "$nome"
    else
      echo "mux: sem multiplexador; rode num terminal à parte:" >&2
      echo "cd '$dir' && $run" >&2
      exit 3
    fi ;;

  ler)
    [ $# -ge 1 ] || uso
    d=$(dono "$1") || exit 1; set -- $d "${2:-80}"
    if [ "$1" = herdr ]; then herdr pane read "$2" --source recent-unwrapped --lines "$3"
    else tm capture-pane -p -J -t "$2" -S "-$3"; fi ;;

  tecla)
    [ $# -eq 2 ] || uso
    k=$2; d=$(dono "$1") || exit 1; set -- $d
    if [ "$1" = herdr ]; then herdr pane send-keys "$2" "$k" >/dev/null
    else tm send-keys -t "$2" "$k"; fi ;;

  manda)
    [ $# -eq 2 ] || uso
    f=$2; [ -f "$f" ] || { echo "mux: não achei o arquivo $f" >&2; exit 1; }
    d=$(dono "$1") || exit 1; set -- $d
    if [ "$1" = herdr ]; then herdr pane send-text "$2" "$(cat "$f")" >/dev/null
    else tm load-buffer -b mux "$f" && tm paste-buffer -d -b mux -t "$2"; fi
    # Um texto colado às vezes fica na caixa: o Enter vai depois de uma pausa.
    sleep 1
    if [ "$1" = herdr ]; then herdr pane send-keys "$2" Enter >/dev/null
    else tm send-keys -t "$2" Enter; fi ;;

  nomear)
    [ $# -ge 2 ] || uso
    nome=$2; id=${3:-}
    d=$(dono "$1") || exit 1; set -- $d
    if [ -n "$id" ]; then
      case_ok=$(printf '%s' "$id" | grep -cE "^$( [ "$1" = tmux ] && echo T || echo H )[0-9]{2}\$" || true)
      [ "$case_ok" = 1 ] || { echo "mux: o id $id não é do $1 (TNN no tmux, HNN no herdr)" >&2; exit 1; }
    fi
    nomeia "$1" "$2" "$nome" $id ;;

  *) uso ;;
esac
