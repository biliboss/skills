#!/usr/bin/env bash
# Google Search Console, read-only: gsc.sh sites | query [--days 28 --by query|page|date --limit 25 --filter page~/x] | sitemaps | inspect <url>
# GSC_KEY (service-account JSON) and GSC_SITE (sc-domain:<domain>) come from the environment. Logic in gsc.py (uv, PEP 723).
set -euo pipefail
exec uv run --script "$(cd "$(dirname "$0")" && pwd)/gsc.py" "$@"
