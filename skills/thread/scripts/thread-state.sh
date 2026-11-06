#!/usr/bin/env bash
# thread-state.sh: the hot path of the threads' realtime state, kept apart so a hook pays for nothing else.
#   thread-state.sh pub <target> [--session]   the target window's state line (or its session's) -> local NATS
# Sourced by thread.sh (state, publish, watch). No forks besides tmux itself: JSON built with printf -v, the NATS
# text protocol spoken on bash's /dev/tcp (CONNECT, PUB…, PING, wait PONG). Event on write, not polling: tmux's own
# control-mode subscriptions (refresh-client -B, %subscription-changed) report "at most once a second" (man tmux 3.7).
# Env: THREAD_NATS_URL (nats://127.0.0.1:4222), THREAD_SUBJECT (mesa.thread.state.changed), THREAD_PUB (a command
# that reads one line instead of NATS: tests), TMUX_SOCKET, TMUX_BIN.
THREAD_NATS_URL="${THREAD_NATS_URL:-nats://127.0.0.1:4222}"
THREAD_SUBJECT="${THREAD_SUBJECT:-mesa.thread.state.changed}"
STATE_FMT='#{session_name}|#{window_index}|#{window_id}|#{@thread}|#{@agent}|#{@ask}|#{@done}|#{@subagents}|#{@touched}|#{@card}|#{window_active}'
if ! declare -F tm >/dev/null; then
  TMUX_BIN="${TMUX_BIN:-}"
  [ -n "$TMUX_BIN" ] || { [ -x /opt/homebrew/bin/tmux ] && TMUX_BIN=/opt/homebrew/bin/tmux || TMUX_BIN=tmux; }
  tm() { if [ -n "${TMUX_SOCKET:-}" ]; then "$TMUX_BIN" -L "$TMUX_SOCKET" "$@"; else "$TMUX_BIN" "$@"; fi; }
fi

_jstr() { # var value: JSON string into var
  local s="${2//\\/\\\\}"; s="${s//\"/\\\"}"; s="${s//$'\t'/ }"; printf -v "$1" '"%s"' "$s"
}
_num() { case "$2" in ''|*[!0-9]*) printf -v "$1" 0 ;; *) printf -v "$1" '%s' "$2" ;; esac; }

to_json() { # STATE_FMT lines on stdin -> JSON lines, threads only
  local sess idx wid th ag ask done subs tch card act st js jt jc ni ns nt
  while IFS='|' read -r sess idx wid th ag ask done subs tch card act; do
    [ -n "$th" ] || continue
    _num ni "$idx"; _num ns "$subs"; _num nt "$tch"; _jstr js "$sess"; _jstr jt "$th"
    if [ -n "$card" ]; then _jstr jc "$card"; else jc=null; fi
    if [ -n "$ask" ]; then st=ask; elif [ -n "$done" ]; then st=done
    elif [ "$ag" = working ] || [ "$ns" -gt 0 ]; then st=working; else st=idle; fi
    [ "$act" = 1 ] && act=true || act=false
    printf '{"session":%s,"index":%s,"window":"%s","topic":%s,"state":"%s","subagents":%s,"touched":%s,"card":%s,"active":%s}\n' \
      "$js" "$ni" "$wid" "$jt" "$st" "$ns" "$nt" "$jc" "$act"
  done
}

state_lines() { tm list-windows "$@" -F "$STATE_FMT" 2>/dev/null | to_json; }        # list-windows args -> lines
state_of() { tm display-message -p -t "$1" "$STATE_FMT" 2>/dev/null | to_json; }      # one window, one tmux call

publish() { # JSON lines on stdin -> one NATS message each
  local lines=() line hp host port msg=""
  while IFS= read -r line; do [ -z "$line" ] || lines[${#lines[@]}]="$line"; done
  [ "${#lines[@]}" -gt 0 ] || return 0
  if [ -n "${THREAD_PUB:-}" ]; then
    for line in "${lines[@]}"; do printf '%s\n' "$line" | eval "$THREAD_PUB"; done; return 0
  fi
  hp="${THREAD_NATS_URL#nats://}"; host="${hp%:*}"; port="${hp##*:}"
  for line in "${lines[@]}"; do msg+="PUB $THREAD_SUBJECT $(LC_ALL=C; echo ${#line})"$'\r\n'"$line"$'\r\n'; done
  exec 7<>"/dev/tcp/$host/$port" 2>/dev/null || return 0     # NATS down: the state still reads, nothing is live
  printf 'CONNECT {"verbose":false,"pedantic":false,"name":"thread-state"}\r\n%sPING\r\n' "$msg" >&7
  while IFS= read -r -t 1 line <&7; do case "$line" in PONG*|-ERR*) break ;; esac; done
  exec 7>&- 7<&-
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  case "${1:-}" in
    pub) [ -n "${2:-}" ] || exit 2
         if [ "${3:-}" = --session ]; then state_lines -t "$(tm display-message -p -t "$2" '#{session_id}')" | publish
         else state_of "$2" | publish; fi ;;
    *) sed -n 2,3p "$0"; exit 2 ;;
  esac
fi
