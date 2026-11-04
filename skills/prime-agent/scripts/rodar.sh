#!/bin/sh
# rodar.sh [args do prime-agent...]: roda o Prime Agent no GLM do coding plan (provedor zai), nunca na assinatura do Claude.
#   A chave é lida de $CASA_GLM_TOKEN_FILE só nesta chamada; DO_NOT_TRACK=1 desliga a telemetria.
#   O modelo vem de $PA_MODEL (padrão glm-5.3-flash).
#   Exemplos:
#     rodar.sh                      # interativo, na pasta atual
#     PA_MODEL=glm-5.3 rodar.sh     # o modelo mais potente
#     rodar.sh --resume <id>        # retoma uma sessão
#     rodar.sh model list           # os modelos, com o zai visível
# Não lê stdin.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "rodar: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
TOKEN="${CASA_GLM_TOKEN_FILE:-$HOME/glm_token}"
BIN="${PRIME_AGENT_BIN:-$HOME/.local/bin/prime-agent}"
[ -s "$TOKEN" ] || { echo "rodar: a chave do GLM não está em $TOKEN (CASA_GLM_TOKEN_FILE no casa.env)" >&2; exit 1; }
[ -x "$BIN" ] || { echo "rodar: falta o $BIN; rode o configurar.sh desta skill" >&2; exit 1; }
modelo="${PA_MODEL:-glm-5.3-flash}"
ZAI_API_KEY="$(cat "$TOKEN")"
export ZAI_API_KEY
export DO_NOT_TRACK=1
case "${1:-}" in
  model|models) exec "$BIN" "$@" ;;
esac
exec "$BIN" --provider zai --model "$modelo" "$@"
