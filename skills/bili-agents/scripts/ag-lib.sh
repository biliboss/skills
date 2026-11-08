#!/usr/bin/env bash
# ag-lib.sh: shared functions of the ag-* tools. Not a command.
# Usage: source "$(dirname "$0")/ag-lib.sh"
#
# The multiplexer is the herdr Desktop, through `hc` (herdr-core): terminals with an address tN and a unique name.
# Neither tmux nor the `herdr` CLI (another server) is used.
#
# Code and data are apart. AG_SKILL is the skill directory (this code, found through any symlink); AG_HOME is the data
# home where the agents live (one folder per agent, plus events, logs and house-global scripts).
#
# Variables (all optional):
#   AG_HOME     the data home (default ~/agents)
#   AG_SKILL    the skill directory (default: found from this file, through symlinks)
#   HC_BIN      the hc binary (default `hc` from PATH)
#   AG_PREFIX   prefix put on the terminal name when looking one up (ag-selftest uses "agt-" so it never meets a real agent)
#   AG_EVENTS   the event queue (default $AG_HOME/events.jsonl)
#   AG_MAP      file name<TAB>folder (default $AG_HOME/.agentes)
#
# Exit codes of every ag-* tool: 0 ok, 1 not found, 2 bad usage, 3 timed out, 4 stopped on a permission prompt.

# _ag_here: the real directory of this file, following symlinks (the tools are symlinked into ~/agents/bin)
_ag_here() {
  local s="${BASH_SOURCE[0]}" d
  while [ -L "$s" ]; do d="$(cd "$(dirname "$s")" && pwd)"; s="$(readlink "$s")"; case "$s" in /*) ;; *) s="$d/$s" ;; esac; done
  (cd "$(dirname "$s")" && pwd -P)
}
AG_SKILL="${AG_SKILL:-$(cd "$(_ag_here)/.." && pwd -P)}"
AG_HOME="${AG_HOME:-$HOME/agents}"
HC_BIN="${HC_BIN:-$(command -v hc || echo hc)}"
AG_PREFIX="${AG_PREFIX:-}"
AG_EVENTS="${AG_EVENTS:-$AG_HOME/events.jsonl}"
AG_MAP="${AG_MAP:-$AG_HOME/.agentes}"

ag_erro() { echo "$(basename "$0"): $*" >&2; }
ag_die()  { local c="$1"; shift; ag_erro "$*"; exit "$c"; }

# o hc do ag-* (um lugar só, para trocar de binário)
ag_hc() { "$HC_BIN" "$@"; }

# ag_dir <agente>: pasta do agente (do mapa .agentes ou $AG_HOME/<agente>)
ag_dir() {
  local nome="$1" d=""
  if [ -f "$AG_MAP" ]; then d="$(awk -F'\t' -v n="$nome" '$1==n{print $2; exit}' "$AG_MAP")"; fi
  printf '%s\n' "${d:-$AG_HOME/$nome}"
}

# ag_terminais: uma linha por terminal vivo do Desktop: endereço<TAB>nome<TAB>agente<TAB>pasta
ag_terminais() {
  ag_hc ls --json 2>/dev/null | jq -r '.terminals[]? | [.address, (.name // ""), (.agent // ""), (.cwd // "")] | @tsv'
}

# ag_pane <agente>: imprime o endereço do terminal (tN). 1 se não achar, 2 se achar mais de um.
# Ordem: 1) terminal com esse nome (hc run --name); 2) terminal rodando o claude dentro da pasta do agente.
ag_pane() {
  local nome="$1" achados n dir todos
  todos="$(ag_terminais)"
  achados="$(printf '%s\n' "$todos" | awk -F'\t' -v n="${AG_PREFIX}${nome}" '$2==n{print $1}')"
  if [ -z "$achados" ] && [ -z "$AG_PREFIX" ]; then
    dir="$(ag_dir "$nome")"
    achados="$(printf '%s\n' "$todos" | awk -F'\t' -v p="$dir" '$3 ~ /claude/ && index($4,p)==1 {print $1}')"
  fi
  n="$(printf '%s\n' "$achados" | grep -c .)"
  [ "$n" -ge 1 ] || return 1
  if [ "$n" -gt 1 ]; then printf '%s\n' "$achados" >&2; return 2; fi
  printf '%s\n' "$achados"
}

# ag_capture <terminal>: o que está na tela do terminal (texto puro)
ag_capture() { ag_hc read "$1" 2>/dev/null; }

# ag_teclas <terminal> <tecla>...: aperta teclas (enter, esc, ctrl+c...)
ag_teclas() { local t="$1"; shift; ag_hc keys "$t" "$@" >/dev/null 2>&1; }

# ag_state <terminal>: imprime o estado do agente a partir do fim da tela.
#   permission  pedido de permissão aberto
#   menu        menu de "/" aberto na caixa de entrada
#   waiting     esperando subagentes ou tarefas em segundo plano
#   working     gerando resposta ou rodando ferramenta
#   unsent      a caixa de entrada tem texto: falta o Enter
#   idle        parado, caixa de entrada livre
# O hc também dá um status (idle|working|blocked), mas mais grosso; mantemos os marcadores da tela.
# Se uma atualização do Claude Code mudar o texto, ajuste só esta função.
ag_state() {
  local pane="$1" tela
  tela="$(ag_capture "$pane" | grep -v '^[[:space:]]*$' | tail -30)"
  if printf '%s\n' "$tela" | tail -22 | grep -qE 'requires approval|Do you want to proceed\?|Esc to cancel · Tab to amend'; then
    echo permission; return 0
  fi
  if printf '%s\n' "$tela" | tail -14 | grep -qE '^[[:space:]]+❯ /[A-Za-z:_-]+[[:space:]]{3,}'; then
    echo menu; return 0
  fi
  if printf '%s\n' "$tela" | tail -14 | grep -qE 'Waiting for [0-9]+ background (agent|task)'; then
    echo waiting; return 0
  fi
  if printf '%s\n' "$tela" | tail -14 | grep -qE '…[[:space:]]*\([0-9]+(s|m)'; then
    echo working; return 0
  fi
  # unsent: a caixa de entrada tem texto (uma linha "❯ texto" logo acima da linha separadora de baixo): falta o Enter
  if printf '%s\n' "$tela" | tail -8 | awk '/^❯ ./{c=1; next} c && /^─/{f=1} {c=0} END{exit !f}'; then
    echo unsent; return 0
  fi
  echo idle
}

# ag_agora: epoch em segundos
ag_agora() { date +%s; }
