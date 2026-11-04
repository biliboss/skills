#!/usr/bin/env bash
# nats-bili.sh: falar com o Bili por um evento do NATS (rotas local e remoto). Chamado pelo bili.sh.
#   nats-bili.sh <local|remoto> pedir <arquivo.md> [de]   publica mesa.agent.request.received; imprime "<trace_id> <desde>"
#   nats-bili.sh <local|remoto> esperar <trace_id> [segundos]   espera o mesa.agent.request.answered desse trace_id (padrão 300 s; sai 124 sem resposta)
#   nats-bili.sh <local|remoto> ler [n]                     as últimas n respostas (padrão 5), a mais antiga primeiro
# O evento segue o schema de libs/local-events (campos exatos, sem campo a mais). Esta skill é genérica e não importa a lib:
# publica com a CLI `nats`. Os valores da casa vêm do casa.env (CASA_BILI_NATS_*); nenhuma senha vai na linha de comando.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
SALVO=$(export -p | grep ' CASA_' || true)   # o que já veio do ambiente ganha do arquivo
[ -f "$CASA" ] && . "$CASA"
eval "$SALVO"
uso() { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 2 ] || uso
rota=$1; cmd=$2; shift 2
RAIZ="${CASA_BILI_NATS_RAIZ:-mesa}"
case "$rota" in
  local)  URL="${CASA_BILI_NATS_LOCAL_URL:-nats://127.0.0.1:4222}"; STREAM="${CASA_BILI_NATS_LOCAL_STREAM:-MESA}" ;;
  remoto)
    URL="${CASA_BILI_NATS_REMOTO_URL:?nats-bili: falta CASA_BILI_NATS_REMOTO_URL em $CASA (veja o casa.env.example)}"
    STREAM="${CASA_BILI_NATS_REMOTO_STREAM:-TAREFAS}"
    if [ -n "${CASA_BILI_NATS_REMOTO_USUARIO:-}" ]; then
      f="${CASA_BILI_NATS_REMOTO_SENHA_FILE:?nats-bili: falta CASA_BILI_NATS_REMOTO_SENHA_FILE em $CASA}"
      [ -r "$f" ] || { echo "nats-bili: não leio o arquivo da senha ($f)" >&2; exit 1; }
      export NATS_USER="$CASA_BILI_NATS_REMOTO_USUARIO" NATS_PASSWORD="$(cat "$f")"
    fi ;;
  *) uso ;;
esac
command -v nats >/dev/null || { echo "nats-bili: falta a CLI nats" >&2; exit 1; }
command -v jq >/dev/null || { echo "nats-bili: falta o jq" >&2; exit 1; }
export NATS_URL="$URL"
RECV="$RAIZ.agent.request.received"; RESP="$RAIZ.agent.request.answered"
AGENTE="${CASA_BILI_AGENTE:-hermes/bili}"

case "$cmd" in
  pedir)
    [ $# -ge 1 ] && [ -f "$1" ] || uso
    de="${2:-${CASA_BILI_DE:-claude}}"
    texto=$(cat "$1")
    # a lib redige segredo ao publicar; aqui a skill recusa, porque não importa a lib
    if printf %s "$texto" | grep -E -q 'sk-[A-Za-z0-9_-]{6,}|ghp_[A-Za-z0-9]{10,}|github_pat_|xox[baprs]-|AKIA[0-9A-Z]{16}|Bearer +[A-Za-z0-9._~+/=-]{8,}|[A-Fa-f0-9]{32,}|(password|token|secret|api[_-]?key) *[=:] *[^ ]'; then
      echo "nats-bili: o pedido parece conter um segredo; tire-o do texto" >&2; exit 3
    fi
    trace=$(openssl rand -hex 8)
    agora=$(date +%s)
    jq -n -c --argjson at "$agora" --arg t "$trace" --arg de "$de" --arg ag "$AGENTE" --arg txt "$texto" \
      '{at:$at, trace_id:$t, source:"router", session_id:"skill-bili", agent:$ag, pane:null, origin:"agent", sender:$de, text:$txt, message_id:0}' \
      | nats pub -J "$RECV" --force-stdin >/dev/null 2>&1 || { echo "nats-bili: não publiquei em $RECV ($URL, stream $STREAM): sem stream que cubra o subject, ou o servidor não responde" >&2; exit 1; }
    echo "$trace $agora"
    ;;
  esperar)
    [ $# -ge 1 ] || uso
    fim=$(( $(date +%s) + ${2:-300} ))
    while [ "$(date +%s)" -lt "$fim" ]; do
      r=$(nats sub "$RESP" --stream "$STREAM" --since "${CASA_BILI_JANELA:-1h}" -T --raw 2>/dev/null \
          | jq -c --arg t "$1" '(if .schema then .data else . end) | select(.trace_id == $t)' | head -n 1 || true)
      if [ -n "$r" ]; then
        printf '%s\n' "$r" | jq -r '"BILI: \(.text)\n— ciclo: \((.lead_time_ms/1000)|floor) s · trace_id: \(.trace_id)"'
        exit 0
      fi
      sleep 2
    done
    echo "nats-bili: sem resposta do Bili para $1 em ${2:-300} s" >&2; exit 124
    ;;
  ler)
    nats sub "$RESP" --stream "$STREAM" --since "${CASA_BILI_JANELA:-1h}" -T --raw 2>/dev/null \
      | jq -r '(if .schema then .data else . end) | select(.trace_id) | "\(.at|floor|todate) \(.trace_id): \(.text)"' | tail -n "${1:-5}"
    ;;
  *) uso ;;
esac
