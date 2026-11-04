#!/bin/sh
# mux.sh: o pouco que a skill pede ao multiplexador, igual no herdr, no tmux ou sem nenhum.
#   qual                          diz qual multiplexador abre panes aqui: herdr, tmux ou nenhum
#   abrir <pasta> <nome> <cmd>    abre um pane à direita deste, sem tirar o foco, roda <cmd> nele e imprime o pane
#   ler <pane> [linhas]           as últimas linhas da tela do pane (padrão 80)
#   tecla <pane> <tecla>          manda uma tecla (Down, Enter, Escape, C-o)
#   manda <pane> <arquivo>        manda o texto do arquivo como uma mensagem e aperta Enter
# O pane diz o multiplexador: TNN é do tmux (o %NN dele, com dois dígitos: %4 vira T04), w..:p.. é do herdr. Assim uma sessão
# conduz panes dos dois. Para abrir, vale $MUX, senão $HERDR_PANE_ID (herdr) ou $TMUX (tmux); sem nenhum,
# abrir imprime o comando para rodar num terminal à parte e sai com 3. Não lê stdin.
set -eu
uso() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso

qual() {
  if [ -n "${MUX:-}" ]; then echo "$MUX"
  elif [ -n "${HERDR_PANE_ID:-}" ]; then echo herdr
  elif [ -n "${TMUX:-}" ]; then echo tmux
  else echo nenhum; fi
}
# de quem é o pane: imprime "tmux %N" ou "herdr <id>"
dono() {
  if printf '%s' "$1" | grep -qE '^T[0-9]+$'; then echo "tmux %$(expr "${1#T}" + 0)"
  elif printf '%s' "$1" | grep -qE '^%[0-9]+$'; then echo "tmux $1"
  else echo "herdr $1"; fi
}
cmd=$1; shift

case "$cmd" in
  qual) qual ;;

  abrir)
    [ $# -eq 3 ] || uso
    dir=$1; nome=$2; run=$3; m=$(qual)
    if [ "$m" = herdr ]; then
      pane=$(herdr pane split "$HERDR_PANE_ID" --direction right --cwd "$dir" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
      [ -n "$pane" ] && [ "$pane" != null ] || { echo "mux: o herdr não devolveu o pane" >&2; exit 1; }
      herdr pane run "$pane" "$run" >/dev/null
      herdr pane rename "$pane" "$nome" >/dev/null
      echo "$pane"
    elif [ "$m" = tmux ]; then
      # O comando vai por send-keys, não como argumento do split: assim o pane sobrevive se ele sair.
      pane=$(command tmux split-window -h -d -c "$dir" -P -F '#{pane_id}' ${TMUX_PANE:+-t "$TMUX_PANE"})
      command tmux select-pane -t "$pane" -T "$nome"
      command tmux send-keys -t "$pane" "$run" Enter
      printf 'T%02d\n' "${pane#%}"
    else
      echo "mux: sem multiplexador; rode num terminal à parte:" >&2
      echo "cd '$dir' && $run" >&2
      exit 3
    fi ;;

  ler)
    [ $# -ge 1 ] || uso
    set -- $(dono "$1") "${2:-80}"
    if [ "$1" = herdr ]; then herdr pane read "$2" --source recent-unwrapped --lines "$3"
    else command tmux capture-pane -p -J -t "$2" -S "-$3"; fi ;;

  tecla)
    [ $# -eq 2 ] || uso
    k=$2; set -- $(dono "$1")
    if [ "$1" = herdr ]; then herdr pane send-keys "$2" "$k" >/dev/null
    else command tmux send-keys -t "$2" "$k"; fi ;;

  manda)
    [ $# -eq 2 ] || uso
    f=$2; [ -f "$f" ] || { echo "mux: não achei o arquivo $f" >&2; exit 1; }
    set -- $(dono "$1")
    if [ "$1" = herdr ]; then herdr pane send-text "$2" "$(cat "$f")" >/dev/null
    else command tmux load-buffer -b prime-agent "$f" && command tmux paste-buffer -d -b prime-agent -t "$2"; fi
    # Um texto colado às vezes fica na caixa: o Enter vai depois de uma pausa.
    sleep 1
    if [ "$1" = herdr ]; then herdr pane send-keys "$2" Enter >/dev/null
    else command tmux send-keys -t "$2" Enter; fi ;;

  *) uso ;;
esac
