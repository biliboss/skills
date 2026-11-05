#!/bin/sh
# mux.sh: o pouco que a skill pede ao multiplexador, igual no herdr, no tmux ou sem nenhum.
#   qual                          diz qual multiplexador está em uso: herdr, tmux ou nenhum
#   abrir <pasta> <nome> <cmd>    abre um pane à direita deste, sem tirar o foco, roda <cmd> nele e imprime o pane
#   ler <pane> [linhas]           as últimas linhas da tela do pane (padrão 80)
#   tecla <pane> <tecla>          manda uma tecla (Down, Enter, Escape, C-o)
#   manda <pane> <arquivo>        manda o texto do arquivo como uma mensagem e aperta Enter
# O multiplexador vem de $MUX, senão de $HERDR_PANE_ID (herdr) ou $TMUX (tmux). Sem nenhum, abrir imprime
# o comando para rodar num terminal à parte e sai com 3. Não lê stdin.
set -eu
uso() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso

qual() {
  if [ -n "${MUX:-}" ]; then echo "$MUX"
  elif [ -n "${HERDR_PANE_ID:-}" ]; then echo herdr
  elif [ -n "${TMUX:-}" ]; then echo tmux
  else echo nenhum; fi
}
m=$(qual)
precisa() { [ "$m" != nenhum ] || { echo "mux: sem multiplexador; abra o pane à mão e use o terminal dele" >&2; exit 3; }; }
cmd=$1; shift

case "$cmd" in
  qual) echo "$m" ;;

  abrir)
    [ $# -eq 3 ] || uso
    dir=$1; nome=$2; run=$3
    if [ "$m" = herdr ]; then
      pane=$(herdr pane split "$HERDR_PANE_ID" --direction right --cwd "$dir" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
      [ -n "$pane" ] && [ "$pane" != null ] || { echo "mux: o herdr não devolveu o pane" >&2; exit 1; }
      herdr pane run "$pane" "$run" >/dev/null
      herdr pane rename "$pane" "$nome" >/dev/null
    elif [ "$m" = tmux ]; then
      # O comando vai por send-keys, não como argumento do split: assim o pane sobrevive se ele sair.
      pane=$(command tmux split-window -h -d -c "$dir" -P -F '#{pane_id}' ${TMUX_PANE:+-t "$TMUX_PANE"})
      command tmux select-pane -t "$pane" -T "$nome"
      command tmux send-keys -t "$pane" "$run" Enter
    else
      echo "mux: sem multiplexador; rode num terminal à parte:" >&2
      echo "cd '$dir' && $run" >&2
      exit 3
    fi
    echo "$pane" ;;

  ler)
    [ $# -ge 1 ] || uso
    precisa; n=${2:-80}
    if [ "$m" = herdr ]; then herdr pane read "$1" --source recent-unwrapped --lines "$n"
    else command tmux capture-pane -p -J -t "$1" -S "-$n"; fi ;;

  tecla)
    [ $# -eq 2 ] || uso
    precisa
    if [ "$m" = herdr ]; then herdr pane send-keys "$1" "$2" >/dev/null
    else command tmux send-keys -t "$1" "$2"; fi ;;

  manda)
    [ $# -eq 2 ] || uso
    precisa; [ -f "$2" ] || { echo "mux: não achei o arquivo $2" >&2; exit 1; }
    if [ "$m" = herdr ]; then herdr pane send-text "$1" "$(cat "$2")" >/dev/null
    else command tmux load-buffer -b prime-agent "$2" && command tmux paste-buffer -d -b prime-agent -t "$1"; fi
    # Um texto colado às vezes fica na caixa: o Enter vai depois de uma pausa.
    sleep 1
    if [ "$m" = herdr ]; then herdr pane send-keys "$1" Enter >/dev/null
    else command tmux send-keys -t "$1" Enter; fi ;;

  *) uso ;;
esac
