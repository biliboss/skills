#!/bin/sh
# mux.sh: o pouco que se pede a um multiplexador, igual no herdr, no tmux ou sem nenhum.
#   qual                          diz qual multiplexador abre panes aqui: herdr, tmux ou nenhum
#   panes                         todos os panes dos dois, um por linha: id, mux, pane, nome, estado
#   abrir <pasta> <nome> <cmd>    abre um pane à direita deste, sem tirar o foco, roda <cmd>, dá o nome e imprime o id
#   ler <pane> [linhas]           as últimas linhas da tela do pane (padrão 80)
#   tecla <pane> <tecla>          manda uma tecla (Down, Enter, Escape, C-o)
#   manda <pane> <arquivo>        manda o texto do arquivo como uma mensagem e aperta Enter
#   fila <pane> <arquivo>         como o manda, mas põe na fila do agente (Tab no Hermes) em vez de desviar o turno em curso
#   nomear <pane> <nome> [ID]     dá o nome "ID - nome" ao pane (sem ID, o próximo livre do multiplexador dele)
#   barra <pane> <comando>        manda um comando com barra (reload, rename x, goal ...): a barra vai como tecla, depois o texto e Enter
#   papeis                        os papéis da mesa (human, router, coordinator, agents) lidos do mesa.toml, e o arquivo usado
#   fecha <pane>                  fecha o pane; no herdr recusa se o agente estiver working (no tmux não há estado, confira com ler)
# Cada pane tem um id de dois dígitos que diz o multiplexador: TNN no tmux (nas opções @tnn/@nome do pane,
# porque o Claude Code sobrescreve o título) e HNN no herdr (no rótulo do pane, "HNN - nome"). <pane> aceita
# o id (T01, H05) ou o id nativo (%4, w5R:p39). Para abrir vale $MUX, senão $HERDR_PANE_ID (herdr) ou $TMUX
# (tmux); sem nenhum, vale o multiplexador de [roles].agents do mesa.toml (se estiver no ar); sem nenhum, abrir imprime o comando para rodar num terminal à parte e sai com 3. Não lê stdin.
set -eu
uso() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso

tm() { command tmux "$@"; }
tem_tmux() { command -v tmux >/dev/null 2>&1 && tm list-panes -a >/dev/null 2>&1; }
tem_herdr() { command -v herdr >/dev/null 2>&1 && herdr pane list >/dev/null 2>&1; }
# A mesa (papéis e multiplexador padrão) vem do mesa.toml do dev/prime-bili (spec: ~/biliboss/scripts/mesa.md); esta skill não
# leva cópia. Ordem: $MESA_TOML, dev/prime-bili/scripts/mesa.toml, scripts/mesa.toml. Sem o arquivo (ou sem python3 >= 3.11),
# vale o comportamento de sempre.
mesa_toml() {
  for c in "${MESA_TOML:-}" "$HOME/biliboss/dev/prime-bili/scripts/mesa.toml" "$HOME/biliboss/scripts/mesa.toml"; do
    [ -n "$c" ] && [ -f "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
# py311: o primeiro python com tomllib (>= 3.11); vazio se não houver
py311() {
  for p in python3 python3.14 python3.13 python3.12 python3.11 /opt/homebrew/bin/python3; do
    command -v "$p" >/dev/null 2>&1 && "$p" -c 'import tomllib' 2>/dev/null && { command -v "$p"; return 0; }
  done
  return 1
}
# cfg <tabela.chave>: o valor de texto ou vazio
cfg() {
  f=$(mesa_toml) || return 0
  py=$(py311) || return 0
  "$py" - "$f" "$1" 2>/dev/null <<'PY' || true
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
for k in sys.argv[2].split("."):
    d = d.get(k) if isinstance(d, dict) else None
print(d if isinstance(d, str) else "")
PY
}
# agentes_mux: herdr ou tmux, o multiplexador de [roles].agents ("herdr", "tmux" ou "herdr:..."); vazio se não diz
agentes_mux() { a=$(cfg roles.agents); a=${a%%:*}; case "$a" in herdr|tmux) echo "$a" ;; esac; }
qual() {
  if [ -n "${MUX:-}" ]; then echo "$MUX"
  elif [ -n "${HERDR_PANE_ID:-}" ]; then echo herdr
  elif [ -n "${TMUX:-}" ]; then echo tmux
  else
    a=$(agentes_mux)
    if [ "$a" = herdr ] && tem_herdr; then echo herdr
    elif [ "$a" = tmux ] && tem_tmux; then echo tmux
    else echo nenhum; fi
  fi
}
# os panes do herdr: pane_id<TAB>rótulo<TAB>estado
herdr_panes() { herdr pane list | jq -r '.result.panes[] | [.pane_id, (.label // ""), .agent_status] | @tsv'; }
# de quem é o pane: imprime "tmux %N" ou "herdr <pane_id>"
dono() {
  case "$1" in human|router|coordinator)
    v=$(cfg "roles.$1")
    case "$v" in
      "") ;;  # sem mesa.toml: o nome do papel não vale como pane
      none) echo "mux: o papel $1 é none no mesa.toml (não há pane)" >&2; exit 1 ;;
      *:*) set -- "${v#*:}" ;;
      *) echo "mux: o papel $1 ($v) não diz o pane (esperado <mux>:<id>)" >&2; exit 1 ;;
    esac ;;
  esac
  if printf '%s' "$1" | grep -qE '^T[0-9]{2}$'; then
    p=$(tm list-panes -a -F '#{pane_id} #{@tnn}' | awk -v t="$1" '$2==t {print $1; exit}')
    [ -n "$p" ] || { echo "mux: nenhum pane do tmux com o id $1" >&2; exit 1; }
    echo "tmux $p"
  elif printf '%s' "$1" | grep -qE '^H[0-9]{2}$'; then
    p=$(herdr_panes | awk -F'\t' -v t="$1" 'index($2, t" - ")==1 {print $1; exit}')
    [ -n "$p" ] || { echo "mux: nenhum pane do herdr com o id $1" >&2; exit 1; }
    echo "herdr $p"
  elif printf '%s' "$1" | grep -qE '^%[0-9]+$'; then echo "tmux $1"
  else echo "$(agentes_mux_ou_herdr) $1"; fi
}
agentes_mux_ou_herdr() { a=$(agentes_mux); echo "${a:-herdr}"; }
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
# registra_envio <para> <arquivo>: deixa no NATS local quem mandou o quê (o sha do texto sem espaços), para o
# prompts.py marcar o prompt como de agente e ligar o trace. Sem o nats ou sem servidor, segue em silêncio.
eu() {
  if [ -n "${TMUX_PANE:-}" ]; then id=$(tm display -p -t "$TMUX_PANE" '#{@tnn}' 2>/dev/null); echo "${id:-$TMUX_PANE}"
  elif [ -n "${HERDR_PANE_ID:-}" ]; then
    l=$(herdr_panes | awk -F'\t' -v p="$HERDR_PANE_ID" '$1==p {print $2; exit}'); printf '%s' "$l" | grep -oE '^H[0-9]{2}' || echo "$HERDR_PANE_ID"
  else echo "${MESA_DE:-?}"; fi
}
registra_envio() {
  command -v nats >/dev/null 2>&1 || return 0
  sha=$(tr -d '[:space:]' < "$2" | shasum -a 256 | cut -c1-32)
  trace=${MESA_TRACE_ID:-$(openssl rand -hex 16)}; span=$(openssl rand -hex 8)
  ev=$(printf '{"de":"%s","para":"%s","em":%s,"sha":"%s","trace_id":"%s","span_id":"%s"}' "$(eu)" "$1" "$(date +%s)" "$sha" "$trace" "$span")
  nats --server "${NATS_URL:-nats://127.0.0.1:4222}" kv put mesa_envios "$sha" "$ev" >/dev/null 2>&1 || return 0
  nats --server "${NATS_URL:-nats://127.0.0.1:4222}" pub "mesa.envio.$(printf '%s' "$1" | tr -c 'A-Za-z0-9_-' '_')" "$ev" >/dev/null 2>&1 || true
}
# envia_tecla <mux> <pane nativo> <tecla> e le_tela <mux> <pane nativo> <linhas>: os dois ramos num lugar só
envia_tecla() { if [ "$1" = herdr ]; then herdr pane send-keys "$2" "$3" >/dev/null; else tm send-keys -t "$2" "$3"; fi; }
le_tela() { if [ "$1" = herdr ]; then herdr pane read "$2" --source recent --lines "$3"; else tm capture-pane -p -J -t "$2" -S "-$3"; fi; }
cmd=$1; shift

case "$cmd" in
  qual) qual ;;

  papeis)
    f=$(mesa_toml) || { echo "mux: sem mesa.toml; vale o padrão (herdr se HERDR_PANE_ID, tmux se TMUX, senão nenhum)"; exit 0; }
    echo "# $f"
    for r in human router coordinator agents; do printf '%s\t%s\n' "$r" "$(cfg "roles.$r")"; done ;;

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
    [ "$m" != herdr ] || [ -n "${HERDR_PANE_ID:-}" ] || m=nenhum   # sem o pane de origem, o herdr não sabe onde dividir
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

  manda|fila)
    [ $# -eq 2 ] || uso
    tecla_fim=Enter
    f=$2; [ -f "$f" ] || { echo "mux: não achei o arquivo $f" >&2; exit 1; }
    registra_envio "$1" "$f"
    d=$(dono "$1") || exit 1; set -- $d
    if [ "$1" = herdr ]; then herdr pane send-text "$2" "$(cat "$f")" >/dev/null
    else tm load-buffer -b mux "$f" && tm paste-buffer -d -b mux -t "$2"; fi
    # Um texto colado às vezes fica na caixa: o Enter vai depois de uma pausa.
    sleep 1
    # fila: o Tab só enfileira com o agente ocupado (o rodapé do Hermes diz "queue a message"/"redirect this turn");
    # com ele parado o Tab não manda nada e o texto fica na caixa, então vai Enter.
    if [ "$cmd" = fila ]; then
      if [ "$1" = herdr ]; then rodape=$(herdr pane read "$2" --source recent-unwrapped --lines 6 2>/dev/null)
      else rodape=$(tm capture-pane -p -J -t "$2" -S -6 2>/dev/null); fi
      if printf '%s' "$rodape" | grep -q -i -E 'queue a message for after|redirect this turn|Tab queues'; then tecla_fim=Tab; fi
    fi
    envia_tecla "$1" "$2" "$tecla_fim"
    # O Enter às vezes não submete: a caixa fica com "[Pasted text". Tenta de novo, até 3 vezes (não vale para a fila).
    if [ "$cmd" = manda ]; then
      n=0
      while [ $n -lt 3 ]; do
        sleep 2
        tela=$(le_tela "$1" "$2" 6 2>/dev/null || true)
        printf '%s' "$tela" | grep -q 'Pasted text' || break
        envia_tecla "$1" "$2" Enter; n=$((n+1))
      done
      [ $n -lt 3 ] || echo "mux: a mensagem pode não ter entrado; confira com: mux.sh ler <pane> 20" >&2
    fi ;;

  nomear)
    [ $# -ge 2 ] || uso
    nome=$2; id=${3:-}
    d=$(dono "$1") || exit 1; set -- $d
    if [ -n "$id" ]; then
      case_ok=$(printf '%s' "$id" | grep -cE "^$( [ "$1" = tmux ] && echo T || echo H )[0-9]{2}\$" || true)
      [ "$case_ok" = 1 ] || { echo "mux: o id $id não é do $1 (TNN no tmux, HNN no herdr)" >&2; exit 1; }
    fi
    nomeia "$1" "$2" "$nome" $id ;;

  barra)
    [ $# -eq 2 ] || uso
    txt=$2; d=$(dono "$1") || exit 1; set -- $d
    envia_tecla "$1" "$2" /
    if [ "$1" = herdr ]; then herdr pane send-text "$2" "$txt" >/dev/null; else tm send-keys -t "$2" -l "$txt"; fi
    envia_tecla "$1" "$2" Enter ;;

  fecha)
    [ $# -eq 1 ] || uso
    d=$(dono "$1") || exit 1; set -- $d
    if [ "$1" = herdr ]; then
      est=$(herdr_panes | awk -F'\t' -v p="$2" '$1==p {print $3; exit}')
      [ -n "$est" ] || { echo "mux: pane $2 não existe" >&2; exit 1; }
      [ "$est" != working ] || { echo "mux: $2 está trabalhando; espere (herdr-events esperar $2 --until idle,done,blocked) antes de fechar" >&2; exit 1; }
      herdr pane close "$2" >/dev/null
    else tm kill-pane -t "$2"; fi ;;

  *) uso ;;
esac
