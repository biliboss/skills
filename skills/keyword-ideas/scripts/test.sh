#!/usr/bin/env bash
# Offline test of suggest.sh and opportunities.sh: a fake gsc.sh with fixture rows and the autocomplete answered by a
# local file on a port of its own. No Google call.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T=$(mktemp -d)
PORT=$((20000 + RANDOM % 20000))
cleanup() { if [ -n "${PID:-}" ]; then kill "$PID" 2>/dev/null; wait "$PID" 2>/dev/null || true; fi; rm -rf "$T"; }
trap cleanup EXIT

# fake search-console: answers `query --by query|page` with fixture rows
cat > "$T/gsc.sh" <<'EOF'
#!/usr/bin/env bash
by=query; while [ $# -gt 0 ]; do [ "$1" = "--by" ] && by=$2; shift; done
if [ "$by" = page ]; then
  echo '{"site":"sc-domain:x","from":"2026-10-01","to":"2026-10-28","by":"page","rows":[
   {"page":"https://x/a","clicks":10,"impressions":2000,"ctr":0.005,"position":8.8},
   {"page":"https://x/b","clicks":30,"impressions":300,"ctr":0.1,"position":3.0},
   {"page":"https://x/c","clicks":0,"impressions":5,"ctr":0,"position":6}]}'
else
  echo '{"site":"sc-domain:x","from":"2026-10-01","to":"2026-10-28","by":"query","rows":[
   {"query":"top","clicks":50,"impressions":400,"ctr":0.125,"position":2.1},
   {"query":"quase","clicks":0,"impressions":66,"ctr":0,"position":6.2},
   {"query":"longe","clicks":0,"impressions":90,"ctr":0,"position":35},
   {"query":"pagina2","clicks":2,"impressions":40,"ctr":0.05,"position":14},
   {"query":"pouca","clicks":0,"impressions":3,"ctr":0,"position":7}]}'
fi
EOF
chmod +x "$T/gsc.sh"
mkdir -p "$T/www"
printf '%s' '["creci",["creci sp","como tirar creci","crecio china","CRECI Jundiaí","quanto custa o creci"],[],{}]' > "$T/www/complete"

python3 -I -m http.server "$PORT" --bind 127.0.0.1 --directory "$T/www" >/dev/null 2>&1 &
PID=$!
for _ in $(seq 1 50); do curl -s -o /dev/null "http://127.0.0.1:$PORT/complete" && break; sleep 0.1; done

fail=0
check() { if echo "$2" | jq -e "$3" >/dev/null; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }

o=$(SEARCH_CONSOLE_SH="$T/gsc.sh" "$HERE/opportunities.sh")
check "window comes from gsc" "$o" '.from == "2026-10-01" and .to == "2026-10-28"'
check "striking distance: 4<pos<=20, enough impressions, by impressions" "$o" '[.striking_distance[].query] == ["quase","pagina2"]'
check "low CTR query: pos<=10, ctr<0.02" "$o" '[.low_ctr_queries[].query] == ["quase"]'
check "low CTR page" "$o" '[.low_ctr_pages[].page] == ["https://x/a"]'
o2=$(SEARCH_CONSOLE_SH="$T/gsc.sh" "$HERE/opportunities.sh" --min-impressions 1 --max-ctr 0.2)
check "thresholds are flags" "$o2" '(.low_ctr_pages | length) == 3'
if SEARCH_CONSOLE_SH=/nao/existe "$HERE/opportunities.sh" >/dev/null 2>&1; then echo "FAIL missing gsc.sh must exit 1"; fail=1; else echo "ok   missing gsc.sh exits non-zero"; fi

s=$(KW_SUGGEST_URL="http://127.0.0.1:$PORT/complete" "$HERE/suggest.sh" creci)
check "suggest drops the text without the seed word" "$s" '.dropped_without_seed == 1 and ([.suggestions[].text] | index("crecio china")) == null'
check "suggest keeps accents and case-insensitive seed" "$s" '[.suggestions[].text] | index("CRECI Jundiaí") != null'
check "suggest marks questions" "$s" '[.suggestions[] | select(.question) | .text] == ["como tirar creci","quanto custa o creci"]'

[ $fail -eq 0 ] && echo "todos os testes passaram" || { echo "falhou"; exit 1; }
