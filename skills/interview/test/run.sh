#!/usr/bin/env bash
# Tests for the queue: one window for two forms, and a timeout that keeps the answers.
# Runs against a throwaway HOME and port, with a fake "open the window" command that logs the URL.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"
export HOME="$T/home"; mkdir -p "$HOME"
export INTERVIEW_PORT="${INTERVIEW_PORT:-8461}"
export INTERVIEW_IDLE_SEC=6
OPENS="$T/opens.log"
cat > "$T/open.sh" <<OPEN
#!/bin/sh
echo "\$1" >> "$OPENS"
OPEN
chmod +x "$T/open.sh"
export INTERVIEW_OPEN_CMD="$T/open.sh"
BASE="http://127.0.0.1:$INTERVIEW_PORT"
fail=0
check() { if eval "$2"; then echo "ok   - $1"; else echo "FAIL - $1"; fail=1; fi; }
jq_state() { curl -s "$BASE/state" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const j=JSON.parse(s);console.log(eval(process.argv[1]))})' "$1"; }
cur_url() { jq_state '(j.current&&j.current.url)||""' 2>/dev/null; }
cur_title() { jq_state '(j.current&&j.current.title)||""' 2>/dev/null; }
post_vendor() { # post_vendor <url-with-token> <route> <json-without-token>
  local origin="${1%%/\?*}" tok="${1##*session=}"
  curl -s -X POST "$origin$2" -H 'Content-Type: application/json' -d "$(node -e 'const b=JSON.parse(process.argv[1]);b.token=process.argv[2];console.log(JSON.stringify(b))' "$3" "$tok")"
}
waitfor() { for _ in $(seq 1 80); do if eval "$1"; then return 0; fi; node -e 'setTimeout(()=>{},250)'; done; return 1; }

echo "== Test 1: two forms at once, one window =="
node "$HERE/interview.ts" "$HERE/test/q1.json" > "$T/a.out" 2> "$T/a.err" &
PA=$!
node "$HERE/interview.ts" "$HERE/test/q2.json" > "$T/b.out" 2> "$T/b.err" &
PB=$!
waitfor '[ -n "$(cur_url)" ]'
FIRST="$(cur_title)"
check "one form on screen ($FIRST)" '[ -n "$FIRST" ]'
waitfor '[ "$(jq_state "j.queue.length")" = 1 ]'
check "the other waits in the queue (1 waiting)" '[ "$(jq_state "j.queue.length")" = 1 ]'
check "exactly one window opened" '[ "$(wc -l < "$OPENS" | tr -d " ")" = 1 ]'
U1="$(cur_url)"
post_vendor "$U1" /submit '{"responses":[{"id":"a","value":{"option":"x"}},{"id":"t","value":"resposta do '"$FIRST"'"}]}'; echo
waitfor '[ "$(cur_title)" != "$FIRST" ] && [ -n "$(cur_url)" ]'
SECOND="$(cur_title)"
check "after submit the page moved on to the other form ($FIRST -> $SECOND)" '[ "$SECOND" != "$FIRST" ] && [ -n "$SECOND" ]'
U2="$(cur_url)"
post_vendor "$U2" /submit '{"responses":[{"id":"a","value":{"option":"y"}},{"id":"t","value":"resposta do '"$SECOND"'"}]}'; echo
wait $PA; RA=$?; wait $PB; RB=$?
check "both processes exit 0 (got $RA, $RB)" '[ $RA = 0 ] && [ $RB = 0 ]'
check "form A got its own answer" 'grep -q "resposta do Form A" "$T/a.out"'
check "form B got its own answer" 'grep -q "resposta do Form B" "$T/b.out"'
check "A did not get B's answer" '! grep -q "resposta do Form B" "$T/a.out"'
check "still exactly one window opened" '[ "$(wc -l < "$OPENS" | tr -d " ")" = 1 ]'
echo "--- A stdout"; cat "$T/a.out"; echo "--- B stdout"; cat "$T/b.out"; echo "--- opens.log"; cat "$OPENS"

echo "== Test 2: timeout 5 keeps the answers =="
node "$HERE/interview.ts" "$HERE/test/q3.json" --timeout 5 --no-open > "$T/c.out" 2> "$T/c.err" &
PC=$!
waitfor '[ "$(cur_title)" = "Form C" ] && [ -n "$(cur_url)" ]'
U3="$(cur_url)"
post_vendor "$U3" /draft '{"responses":[{"id":"a","value":{"option":"y"}},{"id":"t","value":"marcado antes de expirar"}]}'; echo
wait $PC; RC=$?
check "process exits 3 (got $RC)" '[ $RC = 3 ]'
check "stdout shows what was marked" 'grep -q "marcado antes de expirar" "$T/c.out"'
REC="$(grep -o '/[^ ]*\.draft\.json' "$T/c.out" | head -1)"
check "stdout names the recovery file ($REC)" '[ -n "$REC" ] && [ -f "$REC" ]'
check "recovery file has the answer" 'grep -q "marcado antes de expirar" "$REC"'
check "form stays answerable after expiry" '[ -n "$(cur_url)" ]'
U4="$(cur_url)"
post_vendor "$U4" /submit '{"responses":[{"id":"a","value":{"option":"x"}},{"id":"t","value":"respondido tarde"}]}'; echo
waitfor 'grep -q "respondido tarde" "$REC"'
check "late answer landed in the recovery file" 'grep -q "respondido tarde" "$REC" && grep -q answered-late "$REC"'
echo "--- C stdout"; cat "$T/c.out"

echo "== Test 3: idle exit =="
waitfor '! curl -s -m 1 "$BASE/health" >/dev/null'
check "server exits by itself when idle" '! curl -s -m 1 "$BASE/health" >/dev/null'
echo "--- server log"; cat "$HOME/.pi/interview-queue.log"
if [ $fail = 0 ]; then echo ALL OK; else echo SOME FAILED; fi
exit $fail
