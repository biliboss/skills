#!/usr/bin/env bash
# thread.sh: open/list/close a topic thread (a tmux window running a Hermes session) in the session where you are, in one call.
#   thread.sh open <topic> [--card C] [--session S] [--from SESSION_ID | --new] [--profile P] [--cwd DIR] [--brief TEXT | --brief - | --brief-gz B64]
#   thread.sh list
#   thread.sh close <topic> [--session S]
# A thread is a /branch of the Hermes session that invoked the skill ($HERMES_SESSION_ID; --from overrides; --new only when asked).
# The tab opens right after the invoking agent's window (tab 2 for a desktop caller: right after the session's first window).
# The tab opens in the caller's tmux session ($TMUX_PANE's); outside tmux, in the session of the owner's most recently active client; --session overrides. Never a session per card.
# The branch is made OFFLINE by fork.py (Hermes's own SessionDB, Hermes's interpreter): the window only resumes the NEW session, never the live source.
# Env: THREAD_FORK (command: <source-id> <title> --profile P -> new id; default fork.py under Hermes's python), HERMES_PY, TMUX_SOCKET (private server, tests), TMUX_BIN, HERMES_BIN, KANBAN_SH, THREAD_READY_TIMEOUT (s, default 40).
set -euo pipefail

TMUX_BIN="${TMUX_BIN:-$(type -P tmux || true)}"
[ -n "$TMUX_BIN" ] || { echo "thread.sh: tmux not found" >&2; exit 127; }
HERMES_BIN="${HERMES_BIN:-$(type -P hermes || true)}"
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
KANBAN_SH="${KANBAN_SH:-$HERE/../../kanban/scripts/kanban.sh}"
READY_TIMEOUT="${THREAD_READY_TIMEOUT:-40}"

tm() { if [ -n "${TMUX_SOCKET:-}" ]; then "$TMUX_BIN" -L "$TMUX_SOCKET" "$@"; else "$TMUX_BIN" "$@"; fi; }
die() { echo "thread.sh: $*" >&2; exit 1; }
usage() { sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-2}"; }

# sessions as "id<TAB>title" lines (id = last column of `hermes sessions list`)
sessions() {
  "$HERMES_BIN" -p "$PROFILE" sessions list 2>/dev/null |
    awk 'NR>2 && NF>1 { id=$NF; t=$0; sub(/[[:space:]]+[^[:space:]]+[[:space:]]+[^[:space:]]+ [^[:space:]]+[[:space:]]+[^[:space:]]+$/, "", t); print id "\t" t }'
}
session_ids() { sessions | cut -f1 | sort; }

hermes_py() { # the interpreter the `hermes` launcher execs (fork.py needs Hermes's own dependencies)
  [ -z "${HERMES_PY:-}" ] || { printf '%s' "$HERMES_PY"; return; }
  grep -o '/[^ ]*/python3[^ ]*' "$(readlink -f "$HERMES_BIN")" 2>/dev/null | head -1 && return
  local inner; inner="$(grep -o '/[^ "]*/hermes' "$HERMES_BIN" 2>/dev/null | head -1)"
  [ -n "$inner" ] && grep -o '/[^ ]*/python3[^ ]*' "$inner" 2>/dev/null | head -1
}

wait_for() { # pane regex
  local deadline=$((SECONDS + READY_TIMEOUT))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if tm capture-pane -p -t "$1" 2>/dev/null | grep -qiE "$2"; then return 0; fi
    sleep 0.3
  done
  return 1
}

wait_ready() { # pane
  local deadline=$((SECONDS + READY_TIMEOUT))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if tm capture-pane -p -t "$1" 2>/dev/null | grep -qiE 'ready|opus|sonnet'; then return 0; fi
    sleep 0.3
  done
  return 1
}

find_window() { # session topic -> window id
  tm list-windows -t "=$1" -F '#{window_id} #{@thread}' 2>/dev/null | awk -v t="$2" '$2==t {print $1; exit}'
}

target_session() { # explicit -> caller's session -> session of the most recently active client
  if [ -n "${1:-}" ]; then printf '%s' "$1"; return; fi
  local s=""
  if [ -n "${TMUX:-}" ] || [ -n "${TMUX_PANE:-}" ]; then
    s="$(tm display-message -p ${TMUX_PANE:+-t "$TMUX_PANE"} '#{session_name}' 2>/dev/null || true)"
  fi
  if [ -z "$s" ]; then
    s="$(tm list-clients -F '#{client_activity} #{client_session}' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2- || true)"
  fi
  [ -n "$s" ] || die "no tmux session found (not inside tmux and no client attached); pass --session S"
  printf '%s' "$s"
}

cmd_open() {
  [ $# -ge 1 ] || usage
  local topic="$1"; shift
  local mode="" from="" card="" session="" PROFILE="bili" cwd="$PWD" brief="" have_brief=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --from) mode=branch; from="${2:?--from needs a Hermes session id}"; shift ;;
      --new) mode=new ;;
      --card) card="${2:?}"; shift ;;
      --session) session="${2:?}"; shift ;;
      --profile) PROFILE="${2:?}"; shift ;;
      --cwd) cwd="${2:?}"; shift ;;
      --brief) have_brief=1
        if [ "${2:-}" = "-" ]; then brief="$(cat)"; else brief="${2:?}"; fi; shift ;;
      --brief-gz) have_brief=1; brief="$(printf '%s' "${2:?}" | base64 -d | gunzip)"; shift ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done
  [ -n "$HERMES_BIN" ] || die "hermes not found"
  [ -d "$cwd" ] || die "no such directory: $cwd"
  case "$card$topic$session$from" in *[\'\"\\\$\`]*) die "card/topic/session must not contain quotes, \$ or backslashes" ;; esac

  # the card, when named: kanban resolves slug or id (best effort; the id goes on the window as @card)
  local kid="" kout=""
  if [ -n "$card" ]; then
    if [ -x "$KANBAN_SH" ] && kout="$("$KANBAN_SH" show "$card" 2>/dev/null | head -1)" && [ -n "$kout" ]; then
      kid="$(printf '%s' "$kout" | sed -n 's/.*(\([0-9a-f]\{6,\}\))$/\1/p')"
    fi
    [ -n "$kid" ] || echo "thread.sh: kanban does not know '$card'; the window gets no @card" >&2
  fi

  session="$(target_session "$session")"
  tm has-session -t "=$session" 2>/dev/null || die "no tmux session '$session'"
  [ -z "$(find_window "$session" "$topic")" ] || die "thread '$topic' already open in '$session' (thread.sh close $topic --session $session)"

  local title="$topic" ids_before
  [ -z "$card" ] || title="$card · $topic"
  if [ -z "$mode" ]; then mode=branch; from="${HERMES_SESSION_ID:-}"; fi
  if [ "$mode" = branch ] && [ -z "$from" ]; then
    die "HERMES_SESSION_ID is empty: a thread is a /branch of the session that invoked it. Pass --from <session id>, or --new to start a fresh session"
  fi
  ids_before="$(session_ids)"

  # branch OFFLINE first: the window then resumes the new copy, so it is never a second client of a live source
  local hcmd newid=""
  if [ "$mode" = branch ]; then
    if [ -n "${THREAD_FORK:-}" ]; then newid="$($THREAD_FORK "$from" "$title" --profile "$PROFILE")" || die "fork failed for session $from"
    else
      local py; py="$(hermes_py)"; [ -n "$py" ] || die "cannot find Hermes's python (set HERMES_PY)"
      newid="$("$py" -I "$HERE/fork.py" "$from" "$title" --profile "$PROFILE")" || die "fork failed for session $from (nothing opened)"
    fi
    [ -n "$newid" ] || die "fork printed no session id"
    hcmd="$(printf '%q -p %q --resume %q' "$HERMES_BIN" "$PROFILE" "$newid")"
  else
    hcmd="$(printf '%q -p %q' "$HERMES_BIN" "$PROFILE")"
  fi
  # right after the invoking agent's window (the pane's own window when the caller is in this session), else after the session's first
  local after=""
  if [ -n "${TMUX_PANE:-}" ] && [ "$(tm display-message -p -t "$TMUX_PANE" '#{session_name}' 2>/dev/null)" = "$session" ]; then
    after="$(tm display-message -p -t "$TMUX_PANE" '#{window_id}' 2>/dev/null || true)"
  fi
  [ -n "$after" ] || after="$(tm list-windows -t "=$session" -F '#{window_id}' | head -1)"
  local win
  win="$(tm new-window -a -d -P -F '#{window_id}' -t "$after" -n "$topic" -c "$cwd" "$hcmd")"
  tm set-option -w -t "$win" @thread "$topic"
  [ -z "$kid" ] || tm set-option -w -t "$win" @card "$kid"

  wait_ready "$win" || die "Hermes did not get ready in ${READY_TIMEOUT}s (window $win left open)"

  local sid="$newid"
  if [ "$have_brief" = 1 ] && [ -n "$brief" ]; then
    printf '%s' "$brief" | tm load-buffer -b "thread-$topic" -
    tm paste-buffer -p -d -b "thread-$topic" -t "$win"
    sleep 0.3
    tm send-keys -t "$win" Enter
  fi

  # session id: the one that appeared after the window opened
  local deadline=$((SECONDS + 25)) line
  while [ -z "$sid" ] && [ "$SECONDS" -lt "$deadline" ]; do
    line="$(comm -13 <(printf '%s\n' "$ids_before") <(session_ids) | head -1)"
    if [ -n "$line" ]; then sid="$line"; break; fi
    sleep 0.5
  done
  if [ "$mode" = new ] && [ -n "$sid" ]; then
    "$HERMES_BIN" -p "$PROFILE" sessions rename "$sid" "$title" >/dev/null 2>&1 || echo "thread.sh: rename failed for $sid" >&2
  fi
  [ -n "$sid" ] || echo "thread.sh: session id not seen yet (title '$title')" >&2
  echo "window=$session:$topic ($win) title='$title' card=${kid:--} session=${sid:-unknown} mode=$mode"
}

cmd_list() { # session<TAB>topic<TAB>window id<TAB>card, every window marked @thread, across sessions
  local f='#{session_name}	#{@thread}	#{window_id}	#{@card}'
  tm list-windows -a -F "#{?@thread,$f,}" 2>/dev/null | awk -F'\t' 'NF>1' || true
}

cmd_close() {
  [ $# -ge 1 ] || usage
  local topic="$1" session="" hits n; shift
  while [ $# -gt 0 ]; do
    case "$1" in --session) session="${2:?}"; shift ;; *) die "unknown option: $1" ;; esac
    shift
  done
  if [ -n "$session" ]; then hits="$(find_window "$session" "$topic" | sed "s|^|$session\t|")"
  else hits="$(cmd_list | awk -F'\t' -v t="$topic" '$2==t {print $1 "\t" $3}')"; fi
  n="$(printf '%s' "$hits" | grep -c . || true)"
  [ "$n" -ge 1 ] || die "no thread '$topic'"
  [ "$n" -eq 1 ] || die "thread '$topic' is open in more than one session; pass --session S"
  tm kill-window -t "$(printf '%s' "$hits" | cut -f2)"
  echo "closed $topic in $(printf '%s' "$hits" | cut -f1) (the Hermes session stays)"
}

[ $# -gt 0 ] || usage
case "$1" in
  open) shift; cmd_open "$@" ;;
  list) shift; cmd_list "$@" ;;
  close) shift; cmd_close "$@" ;;
  -h|--help|help) usage 0 ;;
  *) usage ;;
esac
