#!/usr/bin/env bash
# Opportunities in our own Search Console data, read-only:
#   opportunities.sh [--days 28] [--min-impressions 20] [--max-ctr 0.02] [--limit 1000]
# Runs the search-console skill's gsc.sh (SEARCH_CONSOLE_SH, else the sibling skill), which reads GSC_KEY and GSC_SITE
# from the environment or the Hermes profile's .env. Logic in kw.py (uv).
set -euo pipefail
exec uv run --quiet --script "$(cd "$(dirname "$0")" && pwd)/kw.py" opportunities "$@"
