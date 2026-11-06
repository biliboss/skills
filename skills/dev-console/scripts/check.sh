#!/usr/bin/env bash
# Headless check of a console page (title, status, errors, an --eval value, a screenshot) with the installed Chrome.
#   check.sh <url> [--shot out.png] [--width 1000] [--height 800] [--wait 1500] [--eval '<js>']
# Exit 0 when the page loaded with no console or page error; 1 otherwise. The logic is in check.py (uv, PEP 723).
set -euo pipefail
exec uv run --script "$(cd "$(dirname "$0")" && pwd)/check.py" "$@"
