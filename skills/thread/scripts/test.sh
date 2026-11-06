#!/usr/bin/env bash
# Tests for thread.sh with a fake hermes and a private tmux server (-L thread-test-<pid>); the owner's server is untouched.
set -uo pipefail
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
unset TMUX TMUX_PANE
export HERMES_SESSION_ID=local-39c1abc  # the invoking agent
export TMUX_SOCKET="thread-test-$$"
export FAKE_DIR; FAKE_DIR="$(mktemp -d)"
export THREAD_READY_TIMEOUT=15
export THREAD_LOG="$FAKE_DIR/threads.log"
TMUXB="$(type -P tmux)"
FAKEBIN="$FAKE_DIR/bin"; mkdir -p "$FAKEBIN"
cp "$HERE/fake_hermes.py" "$FAKEBIN/hermes"; chmod +x "$FAKEBIN/hermes"
export HERMES_BIN="$FAKEBIN/hermes"
cat >"$FAKEBIN/kanban.sh" <<'EOF'
#!/usr/bin/env bash
[ "$2" = "unicred" ] || [ "$2" = "8dbbe594" ] && echo "Unicred  (8dbbe594)" && exit 0
exit 1
EOF
chmod +x "$FAKEBIN/kanban.sh"; export KANBAN_SH="$FAKEBIN/kanban.sh"
# tmux shim: `list-clients` answers from $FAKE_DIR/clients (a private server has no attached client); the rest is real tmux
cat >"$FAKEBIN/tmux" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do [ "\$a" = list-clients ] && { cat "$FAKE_DIR/clients" 2>/dev/null; exit 0; }; done
exec "$TMUXB" "\$@"
EOF
chmod +x "$FAKEBIN/tmux"
# the offline fork: records "<source> <title> <profile>", adds the branch row, prints its id (fails when the source is 'broken')
cat >"$FAKEBIN/fork" <<'EOF'
#!/usr/bin/env bash
[ "$1" = broken ] && { echo "no such session" >&2; exit 1; }
echo "$1|$2|$4" >>"$FAKE_DIR/forks"
n=$(( $(wc -l <"$FAKE_DIR/sessions.tsv" 2>/dev/null || echo 0) + 1 ))
printf 'fork-%s\t%s\n' "$n" "$2" >>"$FAKE_DIR/sessions.tsv"; echo "fork-$n"
EOF
chmod +x "$FAKEBIN/fork"; export THREAD_FORK="$FAKEBIN/fork"
T="$HERE/thread.sh"
cleanup() { "$TMUXB" -L "$TMUX_SOCKET" kill-server 2>/dev/null; rm -rf "$FAKE_DIR"; }
trap cleanup EXIT
pass=0; fail=0
ok() { if [ "$1" = 0 ]; then pass=$((pass+1)); echo "ok   $2"; else fail=$((fail+1)); echo "FAIL $2"; fi; }
tm() { "$TMUXB" -L "$TMUX_SOCKET" "$@"; }
tm new-session -d -s work -n w0; tm new-session -d -s other -n agent0; tm new-window -d -t other: -n agent1; tm new-window -d -t other: -n agent2
printf 'line one\nline two with '"'"'quotes'"'"' and "double" and $VAR\n' >"$FAKE_DIR/brief.txt"

# 1. the caller is inside tmux (TMUX_PANE of its agent window): the tab opens in ITS session, not a per-card one
out="$(tm run-shell -t other:agent1 "TMUX_PANE=$(tm display-message -p -t other:agent1 "#{pane_id}") $T open acesso-bubble --card unicred --brief - <'$FAKE_DIR/brief.txt'" 2>&1)"; echo "  $out"
[ "$(tm list-windows -t =other -F '#{window_name}' | grep -c '^acesso-bubble$')" = 1 ]; ok $? "caller's session: window opened in 'other'"
# the invoking agent was window agent1: the new tab is right after it, the others pushed right
echo "  order: $(tm list-windows -t =other -F "#{window_name}" | paste -sd, -)"
[ "$(tm list-windows -t =other -F '#{window_name}' | paste -sd, -)" = "agent0,agent1,acesso-bubble,agent2" ]; ok $? "placement: right after the invoking agent's window"
grep -qx 'local-39c1abc|unicred · acesso-bubble|bili' "$FAKE_DIR/forks"; ok $? "forks \$HERMES_SESSION_ID offline, titled '<card> · <topic>', profile passed"
grep -q -- '--resume fork-' "$FAKE_DIR/resumed" && ! grep -q 'local-39c1abc' "$FAKE_DIR/resumed"; ok $? "the window resumes the NEW session, never the live source"
tm capture-pane -p -t other:acesso-bubble | grep -q '/branch'; [ $? -ne 0 ]; ok $? "no /branch typed into any window"
tm list-sessions -F '#{session_name}' | grep -qx unicred; [ $? -ne 0 ]; ok $? "no session per card"
sleep 0.5
grep -q "line two with 'quotes' and \"double\" and \$VAR" "$FAKE_DIR/msgs/1"; ok $? "multi-line brief intact, one message"
grep -q "unicred · acesso-bubble" "$FAKE_DIR/sessions.tsv"; ok $? "branch row titled '<card> · <topic>'"
[ "$(tm show-options -wv -t 'other:acesso-bubble' @thread)" = acesso-bubble ]; ok $? "@thread on the window"
[ "$(tm show-options -wv -t 'other:acesso-bubble' @card)" = 8dbbe594 ]; ok $? "@card resolved by slug via kanban"

# 2. outside tmux: the session of the most recently active client
printf '100 work\n300 other\n200 work\n' >"$FAKE_DIR/clients"
out="$(TMUX_BIN="$FAKEBIN/tmux" "$T" open preco --new --brief 'oi')"; echo "  $out"
[ "$(tm list-windows -t =other -F '#{window_name}' | sed -n 2p)" = preco ]; ok $? "desktop caller: right after the session's first window (tab 2)"
tm list-windows -t =other -F '#{window_name}' | grep -qx preco; ok $? "no tmux around: latest client's session ('other')"
grep -qx 'preco' <(cut -f2 "$FAKE_DIR/sessions.tsv"); ok $? "no card: title is the topic alone"
[ -z "$(tm show-options -wv -t 'other:preco' @card)" ]; ok $? "no card: no @card"
printf '500 work\n' >"$FAKE_DIR/clients"
TMUX_BIN="$FAKEBIN/tmux" "$T" open preco --card 8dbbe594 --new >/dev/null
tm list-windows -t =work -F '#{window_name}' | grep -qx preco; ok $? "client moved: opens in 'work'; @card by id"
[ "$(tm show-options -wv -t 'work:preco' @card)" = 8dbbe594 ]; ok $? "@card by id"

# 3. --session overrides; no client and not in tmux fails
"$T" open solto --session work --new >/dev/null; tm list-windows -t =work -F '#{window_name}' | grep -qx solto; ok $? "--session overrides"
: >"$FAKE_DIR/clients"
TMUX_BIN="$FAKEBIN/tmux" "$T" open nada --new >/dev/null 2>&1; [ $? -ne 0 ]; ok $? "no tmux, no client: refused"

# 3b. the owner's focus never moves: the active window is the same before and after `open`
tm select-window -t other:agent0; before="$(tm display-message -p -t =other '#{window_id}')"
"$T" open foco --session other --new >/dev/null
[ "$(tm display-message -p -t =other '#{window_id}')" = "$before" ] && [ "$(tm list-windows -t =other -F '#{window_name}' | sed -n 2p)" = foco ]; ok $? "focus: active window unchanged after open (tab created in the background)"
grep -nE 'select-window|switch-client' "$T" | grep -vE '^[0-9]+: *#' >/dev/null; [ $? -ne 0 ]; ok $? "thread.sh never selects a window or switches the client"

# 4. branch: explicit title, and default when a session titled like the card exists
printf 'unicred-1\tunicred\n' >>"$FAKE_DIR/sessions.tsv"
"$T" open ramo --session work --from unicred-1 --brief 'oi branch' >/dev/null
grep -qx 'unicred-1|ramo|bili' "$FAKE_DIR/forks"; ok $? "--from overrides the invoking session"
! grep -qx -- '--resume unicred-1' "$FAKE_DIR/resumed"; ok $? "--from: the source is never resumed"
sleep 0.5; grep -qx 'oi branch' "$FAKE_DIR/msgs/"* 2>/dev/null; ok $? "branch: brief arrived"
"$T" open padrao --session work --card unicred >/dev/null
grep -q "unicred · padrao" "$FAKE_DIR/sessions.tsv"; ok $? "default is a branch of the invoking session"
"$T" open quebrado --session work --from broken >"$FAKE_DIR/err" 2>&1; rc=$?
[ $rc -ne 0 ] && ! tm list-windows -t =work -F '#{window_name}' | grep -qx quebrado; ok $? "fork failure: refused, nothing opened"
env -u HERMES_SESSION_ID "$T" open recusado --session work >"$FAKE_DIR/err" 2>&1; rc=$?
[ $rc -ne 0 ] && grep -q HERMES_SESSION_ID "$FAKE_DIR/err" && ! tm list-windows -t =work -F '#{window_name}' | grep -qx recusado; ok $? "no HERMES_SESSION_ID, no --from: refused with a clear message, nothing opened"
env -u HERMES_SESSION_ID "$T" open livre --session work --new >/dev/null; ok $? "--new works without HERMES_SESSION_ID"

# 5. 200 KB intact, --brief-gz
head -c 150000 /dev/urandom | base64 | tr -d '\n' | fold -w 100 | head -c 200000 >"$FAKE_DIR/big.txt"
"$T" open grande --session work --new --brief - <"$FAKE_DIR/big.txt" >/dev/null
sleep 1
f="$(grep -l "^$(head -c 40 "$FAKE_DIR/big.txt")" "$FAKE_DIR"/msgs/* | head -1)"
cmp -s <(tr -d '\n' <"$FAKE_DIR/big.txt") <(tr -d '\r\n' <"$f"); ok $? "200 KB brief intact ($(wc -c <"$FAKE_DIR/big.txt") bytes)"
printf 'gz text\nsecond line\n' >"$FAKE_DIR/g.txt"
"$T" open gz --session work --new --brief-gz "$(gzip -c "$FAKE_DIR/g.txt" | base64 | tr -d '\n')" >/dev/null
sleep 0.5; grep -l 'second line' "$FAKE_DIR"/msgs/* >/dev/null; ok $? "--brief-gz round-trip"

# 6. list across sessions / duplicate / close
l="$("$T" list)"; echo "$l" | sed 's/^/  /'
echo "$l" | grep -q '^other	acesso-bubble	.*	8dbbe594$' && echo "$l" | grep -q '^work	preco	'; ok $? "list: windows with @thread across sessions"
"$T" open gz --session work --new >/dev/null 2>&1; [ $? -ne 0 ]; ok $? "duplicate topic in a session refused"
"$T" close gz >/dev/null; ok $? "close by topic"
tm list-windows -t =work -F '#{window_name}' | grep -qx gz; [ $? -ne 0 ]; ok $? "close killed only that window"
grep -q "gz" "$FAKE_DIR/sessions.tsv"; ok $? "close keeps the Hermes session"
"$T" close preco >/dev/null 2>&1; [ $? -ne 0 ]; ok $? "same topic in two sessions: close refused without --session"
"$T" close preco --session other >/dev/null; ok $? "close --session"

# 7. close --self, deferred close when the owner is on the tab, the log line
"$T" open selfie --session work --card unicred --new >/dev/null; sid="$("$T" list | awk -F'\t' '$2=="selfie"{print $3}')"
tm set-option -w -t "$sid" @hsid sess-self
HERMES_SESSION_ID=sess-self "$T" close --self --summary "PR #1 merged" >/dev/null; ok $? "close --self runs"
tm list-windows -t =work -F '#{window_name}' | grep -qx selfie; [ $? -ne 0 ]; ok $? "close --self killed the window"
grep -q . "$FAKE_DIR/sessions.tsv"; ok $? "close --self keeps the Hermes session"
awk -F'\t' '$2=="selfie" && $3=="8dbbe594" && $4=="sess-self" && $5=="PR #1 merged" && $6=="self" && $1 ~ /^20/' "$THREAD_LOG" | grep -q .; ok $? "log line: when, topic, card, session id, summary, by"
"$T" open ficou --session work --new >/dev/null; fid="$("$T" list | awk -F'\t' '$2=="ficou"{print $3}')"
tm set-option -w -t "$fid" @hsid sess-ficou
tm select-window -t "$fid"
HERMES_SESSION_ID=sess-ficou "$T" close --self --summary "feito" | grep -q deferred; ok $? "owner on the tab: close deferred"
tm list-windows -t =work -F '#{window_name}' | grep -qx ficou; ok $? "deferred: window still there while he is on it"
tm select-window -t "=work:1"; "$T" sweep
tm list-windows -t =work -F '#{window_name}' | grep -qx ficou; [ $? -ne 0 ]; ok $? "after he leaves: sweep closes it"
awk -F'\t' '$2=="ficou" && $5=="feito" && $6=="self"' "$THREAD_LOG" | grep -q .; ok $? "deferred close logged"
"$T" open busy --session work --new >/dev/null; bid="$("$T" list | awk -F'\t' '$2=="busy"{print $3}')"
tm set-option -w -t "$bid" @hsid sess-busy; tm set-option -w -t "$bid" @subagents 2
HERMES_SESSION_ID=sess-busy "$T" close --self >/dev/null 2>&1; [ $? -ne 0 ]; ok $? "close --self refused while 2 subagents run"
tm list-windows -t =work -F '#{window_name}' | grep -qx busy; ok $? "...and the window stays"
tm set-option -w -u -t "$bid" @subagents; HERMES_SESSION_ID=sess-busy "$T" close --self --summary ok >/dev/null; ok $? "count 0: close --self runs"
"$T" open conv --session work --new >/dev/null; "$T" close conv --by bili --summary "resolvido" >/dev/null
awk -F'\t' '$2=="conv" && $6=="bili"' "$THREAD_LOG" | grep -q .; ok $? "close <topic> --by bili logged"
HERMES_SESSION_ID=nope "$T" close --self >/dev/null 2>&1; [ $? -ne 0 ]; ok $? "close --self outside a thread refused"

echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
