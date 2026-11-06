#!/usr/bin/env bash
# Google Search Console, read-only: gsc.sh sites | query [--days 28 --by query|page|date --limit 25 --filter page~/x] | sitemaps | inspect <url>
# GSC_KEY (service-account JSON) and GSC_SITE (sc-domain:<domain>) come from the environment; inside a Hermes profile
# they are read from its .env ($HERMES_HOME/.env) when unset, because the agent's terminal does not export that file.
# Logic in gsc.py (uv, PEP 723).
set -euo pipefail
if [ -n "${HERMES_HOME:-}" ] && [ -f "$HERMES_HOME/.env" ]; then
  for k in GSC_KEY GSC_SITE; do
    if [ -z "${!k:-}" ]; then
      v=$(grep -E "^${k}=" "$HERMES_HOME/.env" | tail -1 | cut -d= -f2-)
      [ -n "$v" ] && export "$k=$v"
    fi
  done
fi
exec uv run --script "$(cd "$(dirname "$0")" && pwd)/gsc.py" "$@"
