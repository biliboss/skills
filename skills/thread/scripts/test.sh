#!/usr/bin/env bash
# Tests for thread.sh with a fake hermes and a private tmux server (-L thread-test-<pid>); the owner's server is untouched.
set -uo pipefail
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
export TMUX_SOCKET="thread-test-$$"
export FAKE_DIR; FAKE_DIR="$(mktemp -d)"
export THREAD_READY_TIMEOUT=15
TMUXB="$(type -P tmux)"
FAKEBIN="$FAKE_DIR/bin"; mkdir -p "$FAKEBIN"
cp "$HERE/fake_hermes.py" "$FAKEBIN/hermes"; chmod +x "$FAKEBIN/hermes"
export HERMES_BIN="$FAKEBIN/hermes"
cat >"$FAKEBIN/kanban.sh" <<'EOF'
#!/usr/bin/env bash
[ "$2" = "unicred" ] && echo "Unicred  (8dbbe594)" && exit 0
exit 1
EOF
chmod +x "$FAKEBIN/kanban.sh"; export KANBAN_SH="$FAKEBIN/kanban.sh"
T="$HERE/thread.sh"
cleanup() { "$TMUXB" -L "$TMUX_SOCKET" kill-server 2>/dev/null; rm -rf "$FAKE_DIR"; }
trap cleanup EXIT
pass=0; fail=0
ok() { if [ "$1" = 0 ]; then pass=$((pass+1)); echo "ok   $2"; else fail=$((fail+1)); echo "FAIL $2"; fi; }
tm() { "$TMUXB" -L "$TMUX_SOCKET" "$@"; }

# 1. new + brief on stdin (multi-line is ONE message)
out="$("$T" open unicred acesso-bubble --new --brief - <<'EOF'
line one
line two with 'quotes' and "double" and $VAR
EOF
)"; echo "  $out"
sleep 0.5
[ "$(ls "$FAKE_DIR/msgs" | wc -l | tr -d ' ')" = 1 ]; ok $? "new: brief arrived as one message"
grep -q "line two with 'quotes' and \"double\" and \$VAR" "$FAKE_DIR/msgs/1"; ok $? "new: multi-line content intact"
grep -q "unicred · acesso-bubble" "$FAKE_DIR/sessions.tsv"; ok $? "new: session renamed '<card> · <topic>'"
[ "$(tm show-options -wv -t 'unicred:acesso-bubble' @thread)" = acesso-bubble ]; ok $? "new: @thread set"
[ "$(tm show-options -wv -t 'unicred:acesso-bubble' @card)" = 8dbbe594 ]; ok $? "new: @card from kanban"
tm list-windows -t =unicred -F '#{window_name}' | grep -qx Unicred; ok $? "window 1 named by the kanban title"

# 2. branch (card session exists)
printf 'unicred-1\tunicred\n' >>"$FAKE_DIR/sessions.tsv"
out="$("$T" open unicred preco --branch --brief 'oi branch')"; echo "  $out"
grep -q "unicred · preco" "$FAKE_DIR/sessions.tsv"; ok $? "branch: /branch named the session"
sleep 0.5; grep -qx 'oi branch' "$FAKE_DIR/msgs/2"; ok $? "branch: brief arrived"

# 3. 200 KB intact
head -c 150000 /dev/urandom | base64 | tr -d '\n' | fold -w 100 | head -c 200000 >"$FAKE_DIR/big.txt"
"$T" open unicred grande --new --brief - <"$FAKE_DIR/big.txt" >/dev/null
sleep 1
cmp -s <(tr -d '\n' <"$FAKE_DIR/big.txt") <(tr -d '\r\n' <"$FAKE_DIR/msgs/3"); ok $? "200 KB brief intact ($(wc -c <"$FAKE_DIR/big.txt") bytes)"

# 4. --brief-gz round trip
printf 'gz text\nsecond line\n' >"$FAKE_DIR/g.txt"
"$T" open unicred gz --new --brief-gz "$(gzip -c "$FAKE_DIR/g.txt" | base64 | tr -d '\n')" >/dev/null
sleep 0.5
tr -d '\r' <"$FAKE_DIR/msgs/4" | grep -q 'second line'; ok $? "--brief-gz round-trip"

# 5. list / duplicate / close
n="$("$T" list unicred | wc -l | tr -d ' ')"; [ "$n" = 4 ]; ok $? "list shows 4 threads (got $n)"
"$T" open unicred gz --new >/dev/null 2>&1; [ $? -ne 0 ]; ok $? "duplicate topic refused"
"$T" close unicred gz >/dev/null; ok $? "close"
[ "$("$T" list unicred | wc -l | tr -d ' ')" = 3 ]; ok $? "list after close shows 3"
grep -q "unicred · gz" "$FAKE_DIR/sessions.tsv"; ok $? "close keeps the Hermes session"

echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
