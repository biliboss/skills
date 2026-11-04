#!/bin/sh
# lin.sh <query.graphql | 'query inline'> [variables.json]: GraphQL no Linear com a voz do app Bili.
#   Roda o linear-gql na VPS, como o usuário do Bili e imprime o JSON. Não lê stdin e não imprime token.
#   Cada execução usa arquivos próprios na VPS, então várias podem rodar ao mesmo tempo.
#   Limite de complexidade da API: 10000. Use first:N em toda lista aninhada.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "lin: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_VPS_HOST:?lin: falta CASA_VPS_HOST em $CASA (veja o casa.env.example)}"
: "${CASA_VPS_USUARIO_BILI:?lin: falta CASA_VPS_USUARIO_BILI em $CASA (veja o casa.env.example)}"
[ $# -ge 1 ] || { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
T=lin-$$-$(date +%s)
tmp=""
if [ -f "$1" ]; then q="$1"; else tmp=$(mktemp); printf '%s' "$1" > "$tmp"; q="$tmp"; fi
scp -q "$q" "$CASA_VPS_HOST:/tmp/$T.graphql"
if [ -n "${2:-}" ]; then scp -q "$2" "$CASA_VPS_HOST:/tmp/$T.json"; else ssh -n "$CASA_VPS_HOST" "echo '{}' > /tmp/$T.json"; fi
[ -n "$tmp" ] && rm -f "$tmp"
ssh -n "$CASA_VPS_HOST" "chmod 644 /tmp/$T.graphql /tmp/$T.json; sudo -u $CASA_VPS_USUARIO_BILI sh -c 'linear-gql \"\$(cat /tmp/$T.graphql)\" \"\$(cat /tmp/$T.json)\"'; rm -f /tmp/$T.graphql /tmp/$T.json"
