#!/bin/sh
# agente.sh: o ciclo de vida de uma sessão de agente local, numa aba do herdr no Mac.
#   novo <tema> claude|pi [--foco] [--modelo M] [--retoma ID|ARQUIVO] [--cwd PASTA] [-- args extras do harness]
#        abre a sessão numa aba própria (ou à direita deste pane, com --foco), com o nome do tema.
#        claude: a conta principal do Claude (CASA_CONTA_PRINCIPAL_DIR) com --dangerously-skip-permissions (modelo padrão da conta)
#        pi:     pi-claude.sh <conta principal> --model claude-bridge/<M, padrão claude-opus-5-5> --thinking medium
#   manda <pane> <arquivo>   manda o texto do arquivo como uma mensagem e confere que entrou
#   barra <pane> '<comando>' manda um comando com barra (ex.: 'rename via', 'goal ...', 'reload')
#   fecha <pane>             fecha o pane (e a aba, se ficar vazia), só se a sessão estiver parada
#   foto                     tabela das sessões abertas: tema, pane, harness, id e o comando de retomar
# Não lê stdin.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "agente: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_REPO_PRINCIPAL:?agente: falta CASA_REPO_PRINCIPAL em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_PRINCIPAL_NOME:?agente: falta CASA_CONTA_PRINCIPAL_NOME em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_PRINCIPAL_DIR:?agente: falta CASA_CONTA_PRINCIPAL_DIR em $CASA (veja o casa.env.example)}"

PI_CLAUDE="$(cd "$(dirname "$0")" && pwd)/../../pi/scripts/pi-claude.sh"
uso() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso
cmd=$1; shift

entra_enter() {
  # O Enter às vezes não submete: a caixa fica com "[Pasted text". Tenta de novo, até 3 vezes.
  p=$1; n=0
  while [ $n -lt 3 ]; do
    herdr pane send-keys "$p" Enter >/dev/null
    sleep 2
    herdr pane read "$p" --source recent --lines 6 2>/dev/null | grep -q 'Pasted text' || return 0
    n=$((n + 1))
  done
  echo "agente: a mensagem pode não ter entrado em $p; confira com: herdr pane read $p --source recent --lines 20" >&2
}

case "$cmd" in
  novo)
    [ $# -ge 2 ] || uso
    tema=$1; harness=$2; shift 2
    foco=0; modelo=claude-opus-5-5; retoma=; cwd="$CASA_REPO_PRINCIPAL"; extra=
    while [ $# -gt 0 ]; do
      case "$1" in
        --foco) foco=1 ;;
        --modelo) modelo=$2; shift ;;
        --retoma) retoma=$2; shift ;;
        --cwd) cwd=$2; shift ;;
        --) shift; extra="$*"; break ;;
        *) uso ;;
      esac
      shift
    done
    if [ "$foco" = 1 ]; then
      [ -n "${HERDR_PANE_ID:-}" ] || { echo "agente: --foco precisa de HERDR_PANE_ID (rode de dentro do herdr)" >&2; exit 1; }
      pane=$(herdr pane split "$HERDR_PANE_ID" --direction right --cwd "$cwd" --no-focus | jq -r '[.. | .pane_id? // empty][0]')
    else
      pane=$(herdr tab create --label "$tema" --cwd "$cwd" --no-focus | jq -r '.result.root_pane.pane_id')
    fi
    case "$harness" in
      claude)
        linha="CLAUDE_CONFIG_DIR=$CASA_CONTA_PRINCIPAL_DIR claude --dangerously-skip-permissions"
        [ -z "$retoma" ] || linha="$linha --resume $retoma" ;;
      pi)
        linha="sh $PI_CLAUDE $CASA_CONTA_PRINCIPAL_NOME --model claude-bridge/$modelo --thinking medium"
        if [ -n "$retoma" ]; then linha="$linha --session $retoma"; else linha="$linha --name $tema"; fi ;;
      *) uso ;;
    esac
    [ -z "$extra" ] || linha="$linha $extra"
    herdr pane run "$pane" "$linha" >/dev/null
    herdr pane rename "$pane" "$tema" >/dev/null
    if [ "$harness" = claude ] && [ -z "$retoma" ]; then
      sleep 6
      herdr pane send-keys "$pane" / >/dev/null
      herdr pane send-text "$pane" "rename $tema" >/dev/null
      herdr pane send-keys "$pane" Enter >/dev/null
    fi
    echo "$pane"
    ;;
  manda)
    [ $# -eq 2 ] || uso
    [ -s "$2" ] || { echo "agente: arquivo vazio ou ausente: $2" >&2; exit 1; }
    herdr pane send-text "$1" "$(cat "$2")" >/dev/null
    sleep 1
    entra_enter "$1"
    ;;
  barra)
    [ $# -eq 2 ] || uso
    herdr pane send-keys "$1" / >/dev/null
    herdr pane send-text "$1" "$2" >/dev/null
    entra_enter "$1"
    ;;
  fecha)
    [ $# -eq 1 ] || uso
    est=$(herdr pane list | jq -r --arg p "$1" '.result.panes[] | select(.pane_id == $p) | .agent_status')
    [ -n "$est" ] || { echo "agente: pane $1 não existe" >&2; exit 1; }
    [ "$est" != working ] || { echo "agente: $1 está trabalhando; espere com herdr-events esperar $1 --until idle,done,blocked" >&2; exit 1; }
    herdr pane list | jq -r --arg p "$1" '.result.panes[] | select(.pane_id == $p) | "retomar: \(.label // .terminal_title_stripped) \(.agent) \(.agent_session.value // "sem-id")"'
    herdr pane close "$1" >/dev/null
    ;;
  foto)
    herdr pane list | jq -r '.result.panes[] | select(.agent) | [(.label // .terminal_title_stripped), .pane_id, .agent, .agent_status, (.agent_session.value // "-")] | @tsv'
    ;;
  -h|--help) uso ;;
  *) uso ;;
esac
