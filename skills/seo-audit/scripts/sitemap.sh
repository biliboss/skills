#!/usr/bin/env bash
# The sitemaps of a site, read-only: sitemap.sh <site|sitemap url> [--check] [--max 200]
# Finds them in robots.txt (else /sitemap.xml), follows sitemap indexes, lists the URLs; --check GETs each URL and
# reports status, redirects and X-Robots-Tag noindex. Logic in audit.py (uv).
set -euo pipefail
[ $# -ge 1 ] || { echo "uso: sitemap.sh <site|url do sitemap> [--check] [--max 200]" >&2; exit 2; }
exec uv run --quiet --script "$(cd "$(dirname "$0")" && pwd)/audit.py" sitemap "$@"
