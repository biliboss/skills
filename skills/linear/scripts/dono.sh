#!/bin/sh
# dono.sh <'query inline' | query.graphql> [variables.json]: GraphQL no Linear com a chave pessoal do dono.
#   A chave vem do Keychain do Mac (LINEAR_API_KEY) e nunca é impressa.
#   Use para LER o que é do dono (a inbox, as preferências de notificação) ou para o que só o dono faz
#   (apagar, mudar o workflow). Escrever em nome dele pede o OK dele antes.
set -eu
[ $# -ge 1 ] || { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
K=$(security find-generic-password -s LINEAR_API_KEY -w 2>/dev/null) || { echo "dono: LINEAR_API_KEY não está no Keychain" >&2; exit 1; }
if [ -f "$1" ]; then q=$(cat "$1"); else q="$1"; fi
v='{}'; [ -n "${2:-}" ] && v=$(cat "$2")
body=$(jq -n --arg q "$q" --argjson v "$v" '{query:$q, variables:$v}')
curl -s https://api.linear.app/graphql -H "Authorization: $K" -H 'Content-Type: application/json' -d "$body"
