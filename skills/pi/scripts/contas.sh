#!/bin/sh
# contas.sh [--teste]: mostra que conta do Claude cada pasta tem (e-mail, organização, assinatura), sem token.
#   --teste: também faz o pi responder "ok" por cada conta (Haiku, sem ferramentas), pelo pi-claude-bridge.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "contas: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_CONTA_PRINCIPAL_NOME:?contas: falta CASA_CONTA_PRINCIPAL_NOME em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_PRINCIPAL_DIR:?contas: falta CASA_CONTA_PRINCIPAL_DIR em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_SECUNDARIA_NOME:?contas: falta CASA_CONTA_SECUNDARIA_NOME em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_SECUNDARIA_DIR:?contas: falta CASA_CONTA_SECUNDARIA_DIR em $CASA (veja o casa.env.example)}"
aqui=$(cd "$(dirname "$0")" && pwd)
teste=0; [ "${1:-}" = "--teste" ] && teste=1

for par in "$CASA_CONTA_PRINCIPAL_NOME:$CASA_CONTA_PRINCIPAL_DIR" "$CASA_CONTA_SECUNDARIA_NOME:$CASA_CONTA_SECUNDARIA_DIR"; do
  conta=${par%%:*}; dir=${par#*:}
  echo "== $conta ($dir)"
  if [ ! -d "$dir" ]; then echo "   pasta não existe"; continue; fi
  CLAUDE_CONFIG_DIR="$dir" claude auth status 2>/dev/null \
    | jq -r '"   logado: \(.loggedIn)  e-mail: \(.email // "-")  org: \(.orgName // "-")  assinatura: \(.subscriptionType // "-")"' 2>/dev/null \
    || echo "   claude auth status falhou (rode: CLAUDE_CONFIG_DIR=$dir claude auth login)"
  if [ "$teste" = 1 ]; then
    r=$(timeout 150 "$aqui/pi-claude.sh" "$conta" -p --no-tools --model claude-bridge/claude-haiku-4-5 "Responda só: ok" 2>&1 | tail -1) || true
    echo "   pi: $r"
  fi
done
