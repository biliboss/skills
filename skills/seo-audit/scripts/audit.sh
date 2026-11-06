#!/usr/bin/env bash
# On-page SEO audit of one or more URLs from the raw HTML (no JavaScript), read-only: audit.sh <url> [<url> ...]
# Prints {"pages": [...]} with the facts and the findings (erro, aviso, info) of each page. Logic in audit.py (uv).
set -euo pipefail
[ $# -ge 1 ] || { echo "uso: audit.sh <url> [<url> ...]" >&2; exit 2; }
exec uv run --quiet --script "$(cd "$(dirname "$0")" && pwd)/audit.py" page "$@"
