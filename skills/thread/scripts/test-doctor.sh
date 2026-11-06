#!/usr/bin/env bash
# test-doctor.sh: thread.sh doctor on a PRIVATE tmux server (-L) with a fake state.db. Read-only check of the thread invariant.
set -uo pipefail
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
unset TMUX TMUX_PANE
export TMUX_SOCKET="thread-doctor-$$"
T="$HERE/thread.sh"
tm() { tmux -L "$TMUX_SOCKET" "$@"; }
WORK="$(mktemp -d)"
trap 'tm kill-server 2>/dev/null; rm -rf "$WORK"' EXIT
export THREAD_STATE_DB="$WORK/state.db"
pass=0; fail=0
t() { if [ "$2" = "$3" ]; then pass=$((pass+1)); echo "ok   $1"; else fail=$((fail+1)); echo "FAIL $1: got [$2] want [$3]"; fi; }

sqlite3 "$THREAD_STATE_DB" "create table sessions (id text primary key, title text, ended_at real);
  insert into sessions values ('live1','a',NULL),('live2','b',NULL),('live3','c',NULL),('live4','d',NULL),('dead1','e',1.0);"

# thread <session> <thread> <hsid> <start command>: a window carrying the options, in its own session
mk() { # session thread hsid cmd
  local w; w="$(tm new-session -d -P -F '#{window_id}' -s "$1" "$4; sleep 600")" || return 1
  [ -z "$2" ] || tm set-option -w -t "$w" @thread "$2"
  [ -z "$3" ] || tm set-option -w -t "$w" @hsid "$3"
  printf '%s' "$w"
}
tm new-session -d -s anchor "sleep 600"
mk ok-thread ok-thread live1 "echo hermes -p bili --resume live1" >/dev/null
out="$("$T" doctor)"; rc=$?
t "healthy: exit 0" "$rc" 0
t "healthy: summary" "$out" "ok 1 threads"

wnohsid="$(mk no-hsid no-hsid "" "echo hermes --resume x")"
wunk="$(mk unknown unknown ghost "echo hermes --resume ghost")"
wend="$(mk ended ended dead1 "echo hermes --resume dead1")"
wcont="$(mk cont cont live2 "echo hermes -p bili --continue cont")"
wname="$(mk other-name wanted-name live3 "echo hermes --resume live3")"
wmis="$(mk mismatch mismatch live4 "echo hermes --resume live1")"
wcard="$(mk cardonly "" "" "echo hermes --continue cardonly")"; tm set-option -w -t "$wcard" @card abc123
before="$(tm list-windows -a -F '#{session_name} #{window_id} #{window_active} #{window_index}')"
out="$("$T" doctor)"; rc=$?
after="$(tm list-windows -a -F '#{session_name} #{window_id} #{window_active} #{window_index}')"
t "drift: exit 1" "$rc" 1
t "read-only: nothing moved or renamed" "$after" "$before"
has() { printf '%s\n' "$out" | grep -qE "$1" && echo yes || echo no; }
t "missing @hsid"        "$(has "^drift observability hsid-set no-hsid/$wnohsid:")" yes
t "unknown hsid"         "$(has "^drift environment hsid-in-db unknown/$wunk:")" yes
t "ended hsid"           "$(has "^drift behavior hsid-live ended/$wend:")" yes
t "--continue"           "$(has "^drift environment resume-hsid cont/$wcont:")" yes
t "session-name mismatch" "$(has "^drift environment thread-has-own-session other-name/$wname:")" yes
t "resume of another id" "$(has "^drift environment resume-hsid mismatch/$wmis:")" yes
t "card-only session"    "$(has "^drift architecture card-not-a-session cardonly/$wcard:")" yes
t "healthy thread not flagged" "$(has "^drift .* ok-thread/")" no
t "summary"              "$(printf '%s\n' "$out" | tail -1)" "drift $(printf '%s\n' "$out" | grep -cE '^drift [a-z]+ [a-z-]+ ') of 7"

j="$("$T" doctor --json)"
t "json: one object per finding" "$(printf '%s\n' "$j" | grep -c '^{"dimension"')" "$(printf '%s\n' "$out" | grep -cE '^drift [a-z]+ [a-z-]+ ')"
t "json: fields" "$(printf '%s\n' "$j" | grep -c "\"dimension\":\"behavior\",\"check\":\"hsid-live\",\"status\":\"drift\",\"session\":\"ended\",\"window\":\"$wend\"")" 1

v="$("$T" doctor --verbose | grep -c "^ok ")"
t "verbose prints ok findings" "$([ "$v" -gt 0 ] && echo yes || echo no)" yes
t "default hides ok findings" "$("$T" doctor | grep -c "^ok [a-z]")" 0

mv "$THREAD_STATE_DB" "$WORK/gone.db"
out="$("$T" doctor)"
t "no state.db: warns and skips Hermes checks" "$(printf '%s\n' "$out" | grep -c '^warn environment state-db')/$(printf '%s\n' "$out" | grep -c 'hsid-in-db')" "1/0"

TMUX_SOCKET=thread-doctor-none-$$ "$T" doctor >/dev/null 2>&1
t "no tmux server: exit 2" "$?" 2

echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
