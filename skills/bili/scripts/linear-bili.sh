#!/bin/sh
# linear-bili.sh: falar com o Bili por um cartão do Linear (a menção abre a sessão de agente dele).
#   pedir <cartão> <arquivo.md>            comenta no cartão marcando o Bili, pela conta do dono; imprime "<id> <desde>"
#   esperar <cartão> <desde> [segundos]     espera o primeiro comentário do Bili depois de <desde> (padrão 900 s; sai 124 sem resposta)
#   (BILI_SECO=1 no pedir só imprime a menção, sem comentar)
#   ler <cartão> [n]                        os últimos n comentários do cartão (padrão 6), o mais antigo primeiro
# <cartão> é o identificador (<TIME>-231). A chave é a do dono (o dono.sh da skill linear); nada é impresso dela.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "linear-bili: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_BILI_PERFIL_URL:?linear-bili: falta CASA_BILI_PERFIL_URL em $CASA (veja o casa.env.example)}"
AQUI=$(cd "$(dirname "$0")" && pwd)
G="$AQUI/../../linear/scripts/dono.sh"
[ -f "$G" ] || { echo "linear-bili: não achei o dono.sh da skill linear" >&2; exit 1; }
MENCAO="[@bili]($CASA_BILI_PERFIL_URL)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
uso() { sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

comentarios() { # <cartão> <n>
  jq -n --arg id "$1" --argjson n "$2" '{id:$id, n:$n}' > "$TMP/v.json"
  sh "$G" 'query($id: String!, $n: Int!) { issue(id: $id) { comments(last: $n) { nodes { createdAt body user { name } } } } }' "$TMP/v.json"
}

case "${1:-}" in
  pedir)
    [ $# -eq 3 ] || uso
    if [ "${BILI_SECO:-}" = 1 ]; then   # modo seco: imprime a menção exata e não comenta
      echo "SECO: comentaria no cartão $2: $MENCAO $(cat "$3")"; exit 0
    fi
    jq -n --arg id "$2" --arg b "$MENCAO $(cat "$3")" '{i:{issueId:$id, body:$b}}' > "$TMP/v.json"
    sh "$G" 'mutation($i: CommentCreateInput!) { commentCreate(input: $i) { success comment { id createdAt } } }' "$TMP/v.json" \
      | jq -r 'if .errors then "ERRO " + .errors[0].message else .data.commentCreate.comment | "\(.id) \(.createdAt)" end'
    ;;
  esperar)
    [ $# -ge 3 ] || uso
    fim=$(( $(date +%s) + ${4:-900} ))
    while [ "$(date +%s)" -lt "$fim" ]; do
      r=$(comentarios "$2" 10 | jq -r --arg d "$3" '[.data.issue.comments.nodes[] | select(.user.name == "Bili" and .createdAt > $d)] | first // empty | "\(.createdAt) \(.body)"')
      if [ -n "$r" ]; then
        echo "BILI: ${r#* }"
        a=$(date -j -u -f '%Y-%m-%dT%H:%M:%S' "$(echo "$3" | cut -c1-19)" +%s 2>/dev/null || echo 0)
        b=$(date -j -u -f '%Y-%m-%dT%H:%M:%S' "$(echo "$r" | cut -c1-19)" +%s 2>/dev/null || echo 0)
        [ "$a" -gt 0 ] && echo "— ciclo: $((b - a)) s"
        exit 0
      fi
      sleep 15
    done
    echo "linear-bili: sem resposta do Bili em ${4:-900} s" >&2; exit 124
    ;;
  ler)
    [ $# -ge 2 ] || uso
    comentarios "$2" "${3:-6}" | jq -r '.data.issue.comments.nodes[] | "\(.createdAt[0:16]) \(.user.name): \(.body)"'
    ;;
  *) uso ;;
esac
