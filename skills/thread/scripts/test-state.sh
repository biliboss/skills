#!/usr/bin/env bash
# test-state.sh: thread.sh state / publish / watch on a private tmux server (TMUX_SOCKET), never the owner's.
#   1. state: one JSON line per thread, the right state for ●◆✓/idle, subagents, card
#   2. publish on write: agent-state.sh ask -> a line reaches THREAD_PUB (no NATS needed)
#   3. live (only when the local NATS answers): watch prints the change, latency from the write < 50 ms
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TH="$HERE/thread.sh"; AS="$HERE/../../tmux/scripts/agent-state.sh"
export TMUX_SOCKET="threadstate$$" THREAD_SORT_DEBOUNCE=0 THREAD_ANIM_MS=0
T="tmux -L $TMUX_SOCKET"
W="$(mktemp -d)"; pass=0; fail=0
ok() { if [ "$2" = 1 ]; then echo "ok   $1"; pass=$((pass + 1)); else echo "FAIL $1"; fail=$((fail + 1)); fi; }
now_ms() { if [ -n "${EPOCHREALTIME:-}" ]; then local t="${EPOCHREALTIME/./}"; echo "${t:0:13}"   # bash 5: no fork
           else perl -MTime::HiRes=time -e 'printf "%d", time()*1000'; fi; }
cleanup() { $T kill-server 2>/dev/null; [ -n "${WPID:-}" ] && kill "$WPID" 2>/dev/null; rm -rf "$W"; }
trap cleanup EXIT

$T -f /dev/null new-session -d -s s -n Bili -x 120 -y 10
for n in a b c; do $T new-window -d -t s: -n "$n"; $T set-option -w -t "s:$n" @thread "$n"; done
$T set-option -w -t s:a @agent working; $T set-option -w -t s:b @done 1; $T set-option -w -t s:c @card k1
$T set-option -w -t s:c @subagents 2

out="$("$TH" state)"
ok "state: one line per thread (3)" "$([ "$(printf '%s\n' "$out" | grep -c .)" = 3 ] && echo 1)"
ok "state: a working, b done, c working by subagents" \
  "$([ "$(printf '%s\n' "$out" | jq -r '.topic + "=" + .state' | tr '\n' ' ')" = "a=working b=done c=working " ] && echo 1)"
ok "state: card and subagents" "$(printf '%s\n' "$out" | jq -e 'select(.topic=="c") | .card=="k1" and .subagents==2' >/dev/null && echo 1)"
ok "state <target>: only that window" "$([ "$("$TH" state s:b | jq -r .topic)" = b ] && echo 1)"

: > "$W/pub"
THREAD_PUB="cat >> '$W/pub'" "$AS" ask s:c
for _ in $(seq 1 40); do grep -q '"ask"' "$W/pub" 2>/dev/null && break; sleep 0.05; done
ok "publish on write: ask reaches the sender" "$(jq -e 'select(.topic=="c") | .state=="ask"' "$W/pub" >/dev/null 2>&1 && echo 1)"

NATS_BIN="${NATS_BIN:-$(command -v nats || echo "$HOME/.local/bin/nats")}"
if [ -x "$NATS_BIN" ] && "$NATS_BIN" -s nats://127.0.0.1:4222 rtt >/dev/null 2>&1; then
  export THREAD_SUBJECT="test.thread.state.$$"
  ( "$TH" watch | while IFS= read -r l; do printf '%s\t%s\n' "$(now_ms)" "$l"; done > "$W/watch" ) &
  WPID=$!
  sleep 1.5   # the subscription is up
  "$AS" ask s:a
  for _ in $(seq 1 100); do grep -q '"topic":"a".*"ask"' "$W/watch" 2>/dev/null && break; sleep 0.02; done
  ok "watch: initial snapshot first (3 lines)" "$([ "$(head -3 "$W/watch" | grep -c '"topic"')" = 3 ] && echo 1)"
  ok "watch: agent-state's write arrives live" "$(grep -q '"topic":"a".*"ask"' "$W/watch" && echo 1)"
  # latency of OUR path: the tmux write -> thread-state.sh pub -> NATS -> watch line; median of 5
  lats=()
  for i in 1 2 3 4 5; do
    t0="$(now_ms)"; $T set-option -w -t s:b @touched "$i"; "$HERE/thread-state.sh" pub s:b
    for _ in $(seq 1 100); do grep -q "\"topic\":\"b\".*\"touched\":$i," "$W/watch" && break; sleep 0.005; done
    t1="$(grep "\"topic\":\"b\".*\"touched\":$i," "$W/watch" | head -1 | cut -f1)"
    lats[${#lats[@]}]=$(( ${t1:-99999} - t0 ))
  done
  med="$(printf '%s\n' "${lats[@]}" | sort -n | sed -n 3p)"
  load="$(sysctl -n vm.loadavg | awk '{print int($2)}')"; cpus="$(sysctl -n hw.ncpu)"
  echo "     latency write -> watch line: ${lats[*]} ms (median $med; load $load on $cpus cores)"
  max="${THREAD_STATE_MAX_MS:-50}"
  if [ "$med" -lt "$max" ]; then ok "watch: live, median < ${max} ms" 1
  elif [ "$load" -gt "$cpus" ]; then echo "warn watch: median ${med} ms over ${max} ms, but the machine is overloaded (not counted)"
  else ok "watch: live, median < ${max} ms (${med})" 0; fi
  pkill -f "sub --raw $THREAD_SUBJECT" 2>/dev/null
else echo "skip live NATS checks (no nats CLI or server at 127.0.0.1:4222)"; fi

echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
