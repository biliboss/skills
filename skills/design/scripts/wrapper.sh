#!/usr/bin/env bash
# Os wrappers de um produto (build, conferir, pastas, foto): lê o casa.env e roda o wrapper.ts.
#   wrapper.sh build <produto> [id…] | conferir <produto> | pastas <produto> | foto <produto> [id…] [--saida <pasta>]
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
# shellcheck source=/dev/null
if [ -f "$CASA" ]; then set -a; . "$CASA"; set +a; fi
# o playwright-core da skill, uma vez
[ -d "$AQUI/../node_modules/playwright-core" ] || (cd "$AQUI/.." && bun install --silent)
exec bun run "$AQUI/wrapper.ts" "$@"
