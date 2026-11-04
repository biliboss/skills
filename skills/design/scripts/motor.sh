#!/usr/bin/env bash
# Sobe um agente como o motor do MCP do design-playground.
#   motor.sh claude [--http [--remota]] [args do claude…]
#                                       claude --mcp-config <config temporária>: stdio (sobe o MCP) ou,
#                                       com --http, o /mcp de um servidor que já está de pé
#   motor.sh pi [--http [--remota]] [args do pi…]
#                                       o mesmo com pi --mcp-config (idleTimeout 0)
#   motor.sh http [--remota] [--servidor]
#                                       o endereço do /mcp (Streamable HTTP) e a config de cliente HTTP;
#                                       --remota usa DP_URL_REMOTA (a tailnet); --servidor sobe
#                                       `bun run $DP_DIR/src/main.ts --servidor` se ninguém estiver na porta
# Lê DP_DIR, DP_URL, DP_URL_REMOTA e DP_TOKEN (opcional) do casa.env.
set -euo pipefail
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
# shellcheck source=/dev/null
# O ambiente vence o casa.env (para apontar para outra porta sem mexer nele).
_url="${DP_URL:-}"; _rem="${DP_URL_REMOTA:-}"; _dir="${DP_DIR:-}"
if [ -f "$CASA" ]; then set -a; . "$CASA"; set +a; fi
[ -n "$_url" ] && DP_URL="$_url"; [ -n "$_rem" ] && DP_URL_REMOTA="$_rem"; [ -n "$_dir" ] && DP_DIR="$_dir"
: "${DP_URL:=http://127.0.0.1:5317}"

modo="${1:-}"; shift || true
precisa_dir() { [ -n "${DP_DIR:-}" ] && [ -f "$DP_DIR/src/main.ts" ] || { echo "DP_DIR não aponta para o design-playground (casa.env)" >&2; exit 1; }; }
no_ar() { curl -fsS -m 2 "$1/api/estado" >/dev/null 2>&1; }

config_stdio() { # $1 = idleTimeout ("" para não pôr)
  local arq; arq="$(mktemp "${TMPDIR:-/tmp}/design-playground-mcp.XXXXXX")"
  local extra=""; [ -n "${1:-}" ] && extra=", \"idleTimeout\": $1"
  cat > "$arq" <<EOF
{ "mcpServers": { "design-playground": { "command": "bun", "args": ["run", "$DP_DIR/src/main.ts"]$extra } } }
EOF
  echo "$arq"
}

config_http() { # $1 = a base (DP_URL ou DP_URL_REMOTA), $2 = idleTimeout ("" para não pôr)
  local arq; arq="$(mktemp "${TMPDIR:-/tmp}/design-playground-mcp.XXXXXX")"
  local extra=""; [ -n "${2:-}" ] && extra=", \"idleTimeout\": $2"
  local cab=""
  # shellcheck disable=SC2016 # ${DP_TOKEN} fica literal: o cliente expande, o token não vai para o arquivo
  [ -n "${DP_TOKEN:-}" ] && cab=', "headers": { "Authorization": "Bearer ${DP_TOKEN}" }'
  printf '{ "mcpServers": { "design-playground": { "type": "http", "url": "%s/mcp"%s%s } } }\n' "$1" "$cab" "$extra" > "$arq"
  echo "$arq"
}

agente() { # $1 = claude|pi, depois os args
  local bin="$1"; shift
  local idle=""; [ "$bin" = pi ] && idle=0
  local via=stdio base="$DP_URL"
  while [ $# -gt 0 ]; do
    case "$1" in
      --http) via=http; shift ;;
      --remota) base="${DP_URL_REMOTA:?falta DP_URL_REMOTA no casa.env}"; shift ;;
      *) break ;;
    esac
  done
  local arq
  if [ "$via" = http ]; then
    no_ar "$base" || { echo "ninguém responde em $base: suba com 'motor.sh http --servidor'" >&2; exit 1; }
    arq="$(config_http "$base" "$idle")"
  else
    precisa_dir
    no_ar "$DP_URL" && echo "aviso: já há um servidor em $DP_URL; este vai recusar as ferramentas até o outro sair (use --http para entrar nele)" >&2
    arq="$(config_stdio "$idle")"
  fi
  exec "$bin" --mcp-config "$arq" "$@"
}

case "$modo" in
  claude|pi) agente "$modo" "$@" ;;
  http)
    base="$DP_URL"; servidor=0
    for a in "$@"; do
      case "$a" in
        --remota) base="${DP_URL_REMOTA:?falta DP_URL_REMOTA no casa.env}" ;;
        --servidor) servidor=1 ;;
        *) echo "opção desconhecida: $a" >&2; exit 2 ;;
      esac
    done
    if [ "$servidor" = 1 ]; then
      if no_ar "$DP_URL"; then echo "já no ar: $DP_URL" >&2
      else
        precisa_dir
        log="${TMPDIR:-/tmp}/design-playground-servidor.log"
        nohup bun run "$DP_DIR/src/main.ts" --servidor >"$log" 2>&1 &
        echo "servidor subindo (pid $!, log $log)" >&2
        for _ in $(seq 1 40); do no_ar "$DP_URL" && break; sleep 0.25; done
        no_ar "$DP_URL" || { echo "o servidor não respondeu em $DP_URL; veja $log" >&2; exit 1; }
      fi
    fi
    url="$base/mcp"
    echo "$url"
    if [ -n "${DP_TOKEN:-}" ]; then
      # shellcheck disable=SC2016 # ${DP_TOKEN} fica literal: o cliente expande
      printf '{ "mcpServers": { "design-playground": { "type": "http", "url": "%s", "headers": { "Authorization": "Bearer ${DP_TOKEN}" } } } }\n' "$url"
      echo "(o cabeçalho usa \${DP_TOKEN}: exporte a variável no cliente, não cole o token)" >&2
    else
      printf '{ "mcpServers": { "design-playground": { "type": "http", "url": "%s" } } }\n' "$url"
    fi
    ;;
  *)
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
