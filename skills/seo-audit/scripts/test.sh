#!/usr/bin/env bash
# Offline test of audit.sh and sitemap.sh: serves fixtures on a local port of its own, checks the JSON, stops the server.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T=$(mktemp -d)
PORT=$((20000 + RANDOM % 20000))
B="http://127.0.0.1:$PORT"
cleanup() { if [ -n "${PID:-}" ]; then kill "$PID" 2>/dev/null; wait "$PID" 2>/dev/null || true; fi; rm -rf "$T"; }
trap cleanup EXIT

cat > "$T/good.html" <<EOF
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Apartamentos em Jundiaí: preço por bairro</title>
<meta name="description" content="O preço do metro quadrado em cada bairro de Jundiaí, com os imóveis à venda.">
<meta name="viewport" content="width=device-width">
<link rel="canonical" href="$B/good.html">
<meta property="og:title" content="Apartamentos em Jundiaí"><meta property="og:description" content="Preço por bairro">
<meta property="og:image" content="$B/capa.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BlogPosting","author":{"@type":"Organization"}}</script>
</head><body><h1>Apartamentos em Jundiaí</h1><img src="a.jpg" alt="sala"><img src="b.jpg">
<p>$(printf 'palavra %.0s' $(seq 1 200))</p></body></html>
EOF
cat > "$T/bad.html" <<EOF
<html><head><meta name="robots" content="noindex,follow"><link rel="canonical" href="/missing.html">
<script type="application/ld+json">{nao e json}</script></head><body><h1>a</h1><h1>b</h1></body></html>
EOF
printf 'User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n' "$B" > "$T/robots.txt"
cat > "$T/sitemap.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>$B/sitemap-0.xml</loc></sitemap></sitemapindex>
EOF
cat > "$T/sitemap-0.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>$B/good.html</loc><lastmod>2026-11-01</lastmod></url><url><loc>$B/missing.html</loc></url>
<url><loc>http://10.255.255.1/interno</loc></url><url><loc>file:///etc/hosts</loc></url></urlset>
EOF
cat > "$T/evil.html" <<EOF
<html lang="pt-BR"><head><title>x</title><link rel="canonical" href="file:///etc/hosts"></head><body></body></html>
EOF

python3 -I -m http.server "$PORT" --bind 127.0.0.1 --directory "$T" >/dev/null 2>&1 &
PID=$!
for _ in $(seq 1 50); do curl -s -o /dev/null "$B/robots.txt" && break; sleep 0.1; done

fail=0
check() { # check <name> <json> <jq expression that must be true>
  if echo "$2" | jq -e "$3" >/dev/null; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi
}
codes='[.findings[].code]'

g=$("$HERE/audit.sh" "$B/good.html" | jq '.pages[0]')
check "good: 200, title, canonical self" "$g" '.status == 200 and .title_len > 0 and .canonical != null'
check "good: JSON-LD types" "$g" '.jsonld_types == ["BlogPosting","Organization"]'
check "good: only the alt finding" "$g" "$codes == [\"img-alt\"]"

b=$("$HERE/audit.sh" "$B/bad.html" | jq '.pages[0]')
check "bad: noindex is erro" "$b" '[.findings[] | select(.code=="noindex") | .level] == ["erro"]'
check "bad: title, lang, viewport, og, h1-many" "$b" "$codes | contains([\"title-missing\",\"lang-missing\",\"viewport-missing\",\"og-missing\",\"h1-many\",\"description-missing\"])"
check "bad: canonical to a 404 is canonical-broken" "$b" "$codes | index(\"canonical-broken\") != null"
check "bad: invalid JSON-LD" "$b" "$codes | index(\"jsonld-invalid\") != null"

s=$("$HERE/sitemap.sh" "$B" --check)
check "sitemap: from robots.txt, index followed" "$s" '(.robots_sitemaps | length) == 1 and .total_urls == 4'
check "sitemap: missing, internal and file: URLs are url-status" "$s" "$codes == [\"url-status\",\"url-status\",\"url-status\"]"
check "sitemap: internal and file: are refused, not fetched" "$s" '[.urls[] | select(.status == null)] | length == 2'

e=$("$HERE/audit.sh" "$B/evil.html" | jq '.pages[0]')
check "canonical file: is refused (canonical-broken)" "$e" "$codes | index(\"canonical-broken\") != null"

n=$("$HERE/audit.sh" "http://127.0.0.1:1/" | jq '.pages[0]')
check "unreachable: fetch erro, no crash" "$n" "$codes == [\"fetch\"]"

[ $fail -eq 0 ] && echo "todos os testes passaram" || { echo "falhou"; exit 1; }
