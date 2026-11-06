#!/bin/sh
# agente.sh: o ciclo de vida de uma sessão de agente local (Claude Code ou pi), em qualquer multiplexador. Só fala
# com o pane pelo mux.sh; o que é do herdr está na seção "SOMENTE HERDR" abaixo.
#   novo <tema> claude|pi [--aba] [--modelo M] [--retoma ID|ARQUIVO] [--cwd PASTA] [-- args extras do harness]
#        abre a sessão num pane à direita deste (herdr, tmux), com o nome do tema, e imprime o id (HNN ou TNN).
#        --aba (SOMENTE HERDR): numa aba própria do herdr, em vez de um pane à direita.
#        claude: a conta principal do Claude (CASA_CONTA_PRINCIPAL_DIR) com --dangerously-skip-permissions (modelo padrão da conta)
#        pi:     pi-claude.sh <conta principal> --model claude-bridge/<M, padrão claude-opus-5-5> --thinking medium
#        Sem multiplexador, imprime o comando para rodar num terminal à parte e sai com 3.
#   manda <pane> <arquivo>   manda o texto do arquivo como uma mensagem e confere que entrou
#   barra <pane> '<comando>' manda um comando com barra (ex.: 'rename via', 'goal ...', 'reload')
#   fecha <pane>             fecha o pane, só se a sessão estiver parada (herdr); imprime o id para retomar
#   foto                     os panes abertos (mux.sh panes) e, no herdr, o id da sessão de cada agente
# Não lê stdin.
set -eu
AQUI="$(cd "$(dirname "$0")" && pwd)"
MUXSH="sh $AQUI/mux.sh"
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "agente: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_REPO_PRINCIPAL:?agente: falta CASA_REPO_PRINCIPAL em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_PRINCIPAL_NOME:?agente: falta CASA_CONTA_PRINCIPAL_NOME em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_PRINCIPAL_DIR:?agente: falta CASA_CONTA_PRINCIPAL_DIR em $CASA (veja o casa.env.example)}"

PI_CLAUDE="$AQUI/../../pi/scripts/pi-claude.sh"
uso() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso
cmd=$1; shift

# --- SOMENTE HERDR -------------------------------------------------------------------------------
# Aba própria (--aba) e o id da sessão para retomar vêm do herdr; o tmux não tem nada disso.
herdr_aba() {  # <tema> <pasta> -> pane_id do pane raiz da aba nova
  herdr tab create --label "$1" --cwd "$2" --no-focus | jq -r '.result.root_pane.pane_id'
}
herdr_retomar() {  # <pane nativo ou HNN> -> "retomar: <nome> <harness> <id>"
  nat=$($MUX panes | awk -F'\t' -v p="$1" '$1==p || $3==p {print $3; exit}')
  herdr pane list | jq -r --arg p "${nat:-$1}" '.result.panes[] | select(.pane_id == $p) | "retomar: \(.label // .terminal_title_stripped) \(.agent) \(.agent_session.value // "sem-id")"'
}
# --- fim do SOMENTE HERDR ------------------------------------------------------------------------

case "$cmd" in
  novo)
    [ $# -ge 2 ] || uso
    tema=$1; harness=$2; shift 2
    aba=0; modelo=claude-opus-5-5; retoma=; cwd="$CASA_REPO_PRINCIPAL"; extra=
    while [ $# -gt 0 ]; do
      case "$1" in
        --aba|--foco) [ "$1" = --foco ] || aba=1 ;;  # --foco era o padrão antigo do pane à direita: agora é o padrão
        --modelo) modelo=$2; shift ;;
        --retoma) retoma=$2; shift ;;
        --cwd) cwd=$2; shift ;;
        --) shift; extra="$*"; break ;;
        *) uso ;;
      esac
      shift
    done
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
    if [ "$aba" = 1 ]; then
      [ "$($MUX qual)" = herdr ] || { echo "agente: --aba é só do herdr (qual = $($MUX qual))" >&2; exit 1; }
      pane=$(herdr_aba "$tema" "$cwd")
      herdr pane run "$pane" "$linha" >/dev/null
      id=$($MUX nomear "$pane" "$tema")
    else
      id=$($MUX abrir "$cwd" "$tema" "$linha") || exit $?
    fi
    if [ "$harness" = claude ] && [ -z "$retoma" ]; then
      sleep 6
      $MUX barra "$id" "rename $tema"
    fi
    echo "$id"
    ;;
  manda)
    [ $# -eq 2 ] || uso
    [ -s "$2" ] || { echo "agente: arquivo vazio ou ausente: $2" >&2; exit 1; }
    $MUX manda "$1" "$2"
    ;;
  barra)
    [ $# -eq 2 ] || uso
    $MUX barra "$1" "$2"
    ;;
  fecha)
    [ $# -eq 1 ] || uso
    if [ "$($MUX qual)" = herdr ]; then herdr_retomar "$1" || true; fi
    $MUX fecha "$1"
    ;;
  foto)
    $MUX panes
    if [ "$($MUX qual)" = herdr ]; then
      herdr pane list | jq -r '.result.panes[] | select(.agent) | [(.label // .terminal_title_stripped), .pane_id, .agent, .agent_status, (.agent_session.value // "-")] | @tsv'
    fi
    ;;
  -h|--help) uso ;;
  *) uso ;;
esac
