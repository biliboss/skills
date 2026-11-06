#!/usr/bin/env bash
# Tests for handoff.sh: the thread skill's fake hermes and a private tmux server (-L handoff-test-<pid>).
set -uo pipefail
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
unset TMUX TMUX_PANE HERMES_SESSION_ID
export TMUX_SOCKET="handoff-test-$$"
export FAKE_DIR; FAKE_DIR="$(mktemp -d)"
export HANDOFF_LOG="$FAKE_DIR/sessions.jsonl" HANDOFF_READY_TIMEOUT=15 HANDOFF_IDLE_TIMEOUT=3
export THREAD_SH="$HERE/../../thread/scripts/thread.sh"
TMUXB="$(type -P tmux)"
FAKEBIN="$FAKE_DIR/bin"; mkdir -p "$FAKEBIN"
cp "$HERE/../../thread/scripts/fake_hermes.py" "$FAKEBIN/hermes"; chmod +x "$FAKEBIN/hermes"
export HERMES_BIN="$FAKEBIN/hermes"
cat >"$FAKEBIN/fork" <<'EOF'
#!/usr/bin/env bash
[ "$1" = broken ] && { echo "no such session" >&2; exit 1; }
echo "$1|$2|$4" >>"$FAKE_DIR/forks"; echo "fork-1"
EOF
chmod +x "$FAKEBIN/fork"; export THREAD_FORK="$FAKEBIN/fork"
H="$HERE/handoff.sh"
tm() { "$TMUXB" -L "$TMUX_SOCKET" "$@"; }
trap 'tm kill-server 2>/dev/null; rm -rf "$FAKE_DIR"' EXIT
pass=0; fail=0
ok() { if [ "$1" = 0 ]; then pass=$((pass+1)); echo "ok   $2"; else fail=$((fail+1)); echo "FAIL $2"; fi; }

# a session whose name has a dot (targets must be ids), the agent in tab 1, another tab after it
tm new-session -d -s "sygnal 0.2" -n "Bili" -x 200 -y 30 "$HERMES_BIN -p bili --resume src-1"
tm new-window -d -t "$(tm list-sessions -F '#{session_id}')": -n zsh
W="$(tm list-windows -a -F '#{window_id} #{window_name}' | awk '$2=="Bili"{print $1}')"
P="$(tm display-message -p -t "$W" '#{pane_id}')"
tm set-option -w -t "$W" @hsid src-1
sleep 1

# 1. no session id known: refused, nothing logged
tm set-option -w -u -t "$W" @hsid
out="$("$H" "$P" 2>&1)"; [ $? -ne 0 ] && [ ! -s "$HANDOFF_LOG" ]; ok $? "no session id: refused, nothing logged ($out)"
tm set-option -w -t "$W" @hsid src-1

# 2. the handoff: log, branch right of the agent, then /new + summary in the original
out="$("$H" "$P" 2>&1)"; rc=$?; echo "$out" | sed 's/^/  /'
ok $rc "handoff exits 0"
jq -e 'select(.session_id=="src-1" and .title=="bili")' "$HANDOFF_LOG" >/dev/null; ok $? "log line: session id and title (thread VO: 'Bili' -> 'bili')"
grep -qx 'src-1|bili antes|bili' "$FAKE_DIR/forks"; ok $? "forked src-1 offline as 'bili antes', profile bili"
order="$(tm list-windows -a -F '#{window_name}' | paste -sd, -)"
[ "$order" = "Bili,bili antes,zsh" ]; ok $? "branch tab right of the agent's ($order)"
grep -q -- '--resume fork-1' "$FAKE_DIR/resumed"; ok $? "the branch tab resumes the copy"
[ "$(tm display-message -p '#{window_name}')" = "Bili" ] || [ "$(tm display-message -p -t "$W" '#{window_active}')" = 1 ]; ok $? "focus stays on the agent's tab"
grep -q '/new$' "$FAKE_DIR/msgs/1"; ok $? "original got /new"
grep -q 'fork-1' "$FAKE_DIR/msgs/2" && grep -q 'bili antes' "$FAKE_DIR/msgs/2"; ok $? "then one summary naming the branch and its tab"
"$H" log | grep -q 'hermes -p bili --resume src-1'; ok $? "log lists the resume command"

# 3. mid-turn: nothing cleaned after the idle timeout (log only)
tm new-window -a -d -t "$W" -n busy "printf 'analyzing…\n'; sleep 600"
B="$(tm list-windows -a -F '#{window_id} #{window_name}' | awk '$2=="busy"{print $1}')"; tm set-option -w -t "$B" @hsid src-2
n0="$(wc -l <"$FAKE_DIR/forks")"
"$H" "$B" >/dev/null 2>&1; rc=$?
[ $rc -ne 0 ] && [ "$(wc -l <"$FAKE_DIR/forks")" = "$n0" ]; ok $? "busy agent: refused after the timeout, no fork"
grep -q '"src-2"' "$HANDOFF_LOG"; ok $? "busy agent: still logged first"

# 4. fork fails: the original is not cleaned
m0="$(ls "$FAKE_DIR/msgs" | wc -l)"
"$H" "$P" --from broken >/dev/null 2>&1; rc=$?
[ $rc -ne 0 ] && [ "$(ls "$FAKE_DIR/msgs" | wc -l)" = "$m0" ]; ok $? "fork failure: nothing sent to the original"

echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
