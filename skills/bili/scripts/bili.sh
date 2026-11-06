#!/usr/bin/env bash
# bili.sh: a única porta para falar com o Bili. A rota vem do casa.env (CASA_BILI_ROTA=local|remoto|linear; padrão local).
#   rota [local|remoto|linear]        mostra a rota de agora; com argumento, grava CASA_BILI_ROTA no casa.env
#   pedir <arquivo.md>                local e remoto: publica o pedido; imprime "<trace_id> <desde>"
#   pedir <cartão> <arquivo.md>       linear: menção ao Bili no cartão; imprime "<id do comentário> <desde>"
#   esperar <trace_id> [segundos]     local e remoto: espera a resposta (evento answered)
#   esperar <cartão> <desde> [seg]    linear: espera o comentário do Bili
#   ler [n]                           local e remoto: as últimas n respostas
#   ler <cartão> [n]                  linear: os últimos n comentários do cartão
# BILI_ROTA=<rota> numa chamada vale só para ela (nada é gravado). BILI_SECO=1 na rota linear só imprime a menção.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
AQUI=$(cd "$(dirname "$0")" && pwd)
SALVO=$(export -p | grep ' CASA_' || true)
[ -f "$CASA" ] && . "$CASA"
eval "$SALVO"
ROTA="${BILI_ROTA:-${CASA_BILI_ROTA:-local}}"
uso() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
valida() { case "$1" in local|remoto|linear) ;; *) echo "bili: rota '$1' desconhecida (local, remoto ou linear)" >&2; exit 2 ;; esac; }
[ $# -ge 1 ] || uso
cmd=$1; shift

if [ "$cmd" = rota ]; then
  if [ $# -eq 0 ]; then
    origem=padrão
    [ -n "${CASA_BILI_ROTA:-}" ] && origem="CASA_BILI_ROTA"
    [ -n "${BILI_ROTA:-}" ] && origem="BILI_ROTA (só esta chamada)"
    echo "$ROTA ($origem; arquivo $CASA)"
    exit 0
  fi
  valida "$1"
  mkdir -p "$(dirname "$CASA")"; touch "$CASA"
  tmp=$(mktemp "$CASA.XXXXXX")
  grep -v '^CASA_BILI_ROTA=' "$CASA" > "$tmp" || true
  echo "CASA_BILI_ROTA=$1" >> "$tmp"
  chmod "$(stat -f %Lp "$CASA" 2>/dev/null || stat -c %a "$CASA")" "$tmp"
  mv "$tmp" "$CASA"
  echo "rota: $1 (gravada em $CASA)"
  exit 0
fi

valida "$ROTA"
case "$cmd" in pedir|esperar|ler) ;; *) uso ;; esac
case "$ROTA" in
  linear) exec sh "$AQUI/linear-bili.sh" "$cmd" "$@" ;;
  *)      exec bash "$AQUI/nats-bili.sh" "$ROTA" "$cmd" "$@" ;;
esac
