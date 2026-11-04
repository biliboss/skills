#!/bin/sh
# mux.sh: o pouco que a skill pede ao multiplexador, igual no herdr, no tmux ou sem nenhum.
#   qual                          diz qual multiplexador abre panes aqui: herdr, tmux ou nenhum
#   abrir <pasta> <nome> <cmd>    abre um pane à direita deste, sem tirar o foco, roda <cmd> nele e imprime o pane
#   ler <pane> [linhas]           as últimas linhas da tela do pane (padrão 80)
#   tecla <pane> <tecla>          manda uma tecla (Down, Enter, Escape, C-o)
#   manda <pane> <arquivo>        manda o texto do arquivo como uma mensagem e aperta Enter
#   nomear <pane> <nome> [TNN]    dá o nome "TNN - nome" a um pane do tmux (sem TNN, o próximo livre)
# O pane diz o multiplexador: TNN (dois dígitos) é um pane do tmux, achado pela opção @tnn dele; w..:p.. é do herdr.
# Assim uma sessão conduz panes dos dois. O nome mora em @tnn/@nome, não no título, que o Claude Code sobrescreve. Para abrir, vale $MUX, senão $HERDR_PANE_ID (herdr) ou $TMUX (tmux); sem nenhum,
# abrir imprime o comando para rodar num terminal à parte e sai com 3. Não lê stdin.
set -eu
uso() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso

qual() {
  if [ -n "${MUX:-}" ]; then echo "$MUX"
  elif [ -n "${HERDR_PANE_ID:-}" ]; then echo herdr
  elif [ -n "${TMUX:-}" ]; then echo tmux
  else echo nenhum; fi
}
# de quem é o pane: imprime "tmux %N" ou "herdr <id>"
dono() {
  if printf '%s' "$1" | grep -qE '^T[0-9]{2}$'; then
    p=$(command tmux list-panes -a -F '#{pane_id} #{@tnn}' | awk -v t="$1" '$2==t {print $1; exit}')
    [ -n "$p" ] || { echo "mux: nenhum pane do tmux com @tnn=$1" >&2; exit 1; }
    echo "tmux $p"
  elif printf '%s' "$1" | grep -qE '^%[0-9]+$'; then echo "tmux $1"
  else echo "herdr $1"; fi
}
# o próximo TNN livre entre os panes do tmux
livre() {
  n=1
  while command tmux list-panes -a -F '#{@tnn}' | grep -qx "$(printf 'T%02d' $n)"; do n=$((n+1)); done
  printf 'T%02d' $n
}
# nomeia <%id> <nome> [TNN]: grava @tnn e @nome no pane e imprime o TNN
nomeia() {
  tnn=${3:-$(livre)}
  command tmux set -p -t "$1" @tnn "$tnn"
  command tmux set -p -t "$1" @nome "$2"
  echo "$tnn"
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
      command tmux send-keys -t "$pane" "$run" Enter
      nomeia "$pane" "$nome"
    else
      echo "mux: sem multiplexador; rode num terminal à parte:" >&2
      echo "cd '$dir' && $run" >&2
      exit 3
    fi ;;

  ler)
    [ $# -ge 1 ] || uso
    d=$(dono "$1") || exit 1; set -- $d "${2:-80}"
    if [ "$1" = herdr ]; then herdr pane read "$2" --source recent-unwrapped --lines "$3"
    else command tmux capture-pane -p -J -t "$2" -S "-$3"; fi ;;

  tecla)
    [ $# -eq 2 ] || uso
    k=$2; d=$(dono "$1") || exit 1; set -- $d
    if [ "$1" = herdr ]; then herdr pane send-keys "$2" "$k" >/dev/null
    else command tmux send-keys -t "$2" "$k"; fi ;;

  manda)
    [ $# -eq 2 ] || uso
    f=$2; [ -f "$f" ] || { echo "mux: não achei o arquivo $f" >&2; exit 1; }
    d=$(dono "$1") || exit 1; set -- $d
    if [ "$1" = herdr ]; then herdr pane send-text "$2" "$(cat "$f")" >/dev/null
    else command tmux load-buffer -b prime-agent "$f" && command tmux paste-buffer -d -b prime-agent -t "$2"; fi
    # Um texto colado às vezes fica na caixa: o Enter vai depois de uma pausa.
    sleep 1
    if [ "$1" = herdr ]; then herdr pane send-keys "$2" Enter >/dev/null
    else command tmux send-keys -t "$2" Enter; fi ;;

  nomear)
    [ $# -ge 2 ] || uso
    d=$(dono "$1") || exit 1; set -- $d "$2" "${3:-}"
    [ "$1" = tmux ] || { echo "mux: nomear é só para o tmux; no herdr, herdr pane rename" >&2; exit 1; }
    nomeia "$2" "$3" ${4:+"$4"} ;;

  *) uso ;;
esac
