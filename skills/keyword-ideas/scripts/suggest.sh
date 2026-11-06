#!/usr/bin/env bash
# Google autocomplete for one or more seeds, read-only: suggest.sh <seed> [<seed> ...] [--expand] [--hl pt-BR] [--gl br]
# --expand also asks for "<seed> a".."<seed> z" and "como|quanto|qual|... <seed>". Logic in kw.py (uv).
set -euo pipefail
[ $# -ge 1 ] || { echo "uso: suggest.sh <semente> [<semente> ...] [--expand]" >&2; exit 2; }
exec uv run --quiet --script "$(cd "$(dirname "$0")" && pwd)/kw.py" suggest "$@"
