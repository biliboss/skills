#!/bin/sh
# Acha em que cofre envless mora uma chave, sem nunca mostrar valor.
# Uso: sh acha-chave.sh '<regex de nome>' [raiz]   ex.: sh acha-chave.sh 'cloudflare|^cf_'
# Percorre toda pasta com .envless/ (até 5 níveis) e lista, por ambiente, só os NOMES que casam.
padrao="${1:?regex do nome da chave}"
raiz="${2:-$HOME}"
for c in $(find "$raiz" -maxdepth 5 -type d -name .envless -not -path '*/node_modules/*' -not -path '/tmp/*' 2>/dev/null); do
  d=$(dirname "$c")
  for f in "$d"/secrets/*.env.enc; do
    [ -e "$f" ] || continue
    e=$(basename "$f" .env.enc)
    k=$(cd "$d" && envless list --env="$e" 2>/dev/null | grep -i -E "$padrao" | tr '\n' ' ')
    [ -n "$k" ] && echo "$d [$e]: $k"
  done
done
echo fim
