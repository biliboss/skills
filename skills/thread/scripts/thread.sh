#!/usr/bin/env bash
# thread.sh: open/list/close a topic thread of a card (a tmux window running a Hermes session), in one call.
#   thread.sh open <card-slug> <topic> [--branch|--new] [--profile P] [--cwd DIR] [--brief TEXT | --brief - | --brief-gz B64]
#   thread.sh list [<card-slug>]
#   thread.sh close <card-slug> <topic>
# Env: TMUX_SOCKET (private server, tests), TMUX_BIN, HERMES_BIN, KANBAN_SH, THREAD_READY_TIMEOUT (s, default 40).
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

cmd_open() {
  [ $# -ge 2 ] || usage
  local card="$1" topic="$2"; shift 2
  local mode="" PROFILE="bili" cwd="$PWD" brief="" have_brief=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --branch) mode=branch ;;
      --new) mode=new ;;
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
  case "$card$topic" in *[\'\"\\\$\`]*) die "card/topic must not contain quotes, \$ or backslashes" ;; esac

  # kanban knows the card? (best effort: title for window 1, id for @card)
  local ktitle="" kid="" kout=""
  if [ -x "$KANBAN_SH" ] && kout="$("$KANBAN_SH" show "$card" 2>/dev/null | head -1)" && [ -n "$kout" ]; then
    kid="$(printf '%s' "$kout" | sed -n 's/.*(\([0-9a-f]\{6,\}\))$/\1/p')"
    ktitle="$(printf '%s' "$kout" | sed 's/  ([0-9a-f]*)$//')"
  fi

  local title="$card · $topic" ids_before
  if [ -z "$mode" ]; then
    if sessions | cut -f2- | grep -qxF "$card"; then mode=branch; else mode=new; fi
  fi
  ids_before="$(session_ids)"

  if ! tm has-session -t "=$card" 2>/dev/null; then
    tm new-session -d -s "$card" -n "${ktitle:-$card}" -c "$cwd"
  fi
  [ -z "$(find_window "$card" "$topic")" ] || die "thread '$topic' already open in '$card' (thread.sh close $card $topic)"

  local hcmd
  if [ "$mode" = branch ]; then
    hcmd="$(printf '%q -p %q --continue %q' "$HERMES_BIN" "$PROFILE" "$card")"
  else
    hcmd="$(printf '%q -p %q' "$HERMES_BIN" "$PROFILE")"
  fi
  local win
  win="$(tm new-window -d -P -F '#{window_id}' -t "=$card:" -n "$topic" -c "$cwd" "$hcmd")"
  tm set-option -w -t "$win" @thread "$topic"
  [ -z "$kid" ] || tm set-option -w -t "$win" @card "$kid"

  wait_ready "$win" || die "Hermes did not get ready in ${READY_TIMEOUT}s (window $win left open)"

  local sid=""
  if [ "$mode" = branch ]; then
    tm send-keys -t "$win" -l "/branch $title"; tm send-keys -t "$win" Enter
  fi
  if [ "$have_brief" = 1 ] && [ -n "$brief" ]; then
    [ "$mode" = branch ] && sleep 1.5
    printf '%s' "$brief" | tm load-buffer -b "thread-$topic" -
    tm paste-buffer -p -d -b "thread-$topic" -t "$win"
    sleep 0.3
    tm send-keys -t "$win" Enter
  fi

  # session id: the one that appeared after the window opened
  local deadline=$((SECONDS + 25)) line
  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ "$mode" = branch ]; then
      line="$(sessions | awk -F'\t' -v t="$title" '$2==t {print $1; exit}')"
    else
      line="$(comm -13 <(printf '%s\n' "$ids_before") <(session_ids) | head -1)"
    fi
    if [ -n "$line" ]; then sid="$line"; break; fi
    sleep 0.5
  done
  if [ "$mode" = new ] && [ -n "$sid" ]; then
    "$HERMES_BIN" -p "$PROFILE" sessions rename "$sid" "$title" >/dev/null 2>&1 || echo "thread.sh: rename failed for $sid" >&2
  fi
  [ -n "$sid" ] || echo "thread.sh: session id not seen yet (title '$title')" >&2
  echo "window=$card:$topic ($win) title='$title' session=${sid:-unknown} mode=$mode"
}

cmd_list() {
  local f='#{session_name}	#{window_name}	#{window_id}	#{@card}'
  tm list-windows -a -F "#{?@thread,$f,}" 2>/dev/null | awk -F'\t' -v c="${1:-}" 'NF>1 && (c=="" || $1==c)' || true
}

cmd_close() {
  [ $# -eq 2 ] || usage
  local win; win="$(find_window "$1" "$2")"
  [ -n "$win" ] || die "no thread '$2' in '$1'"
  tm kill-window -t "$win"
  echo "closed $1:$2 (the Hermes session stays)"
}

[ $# -gt 0 ] || usage
sub="$1"; shift
case "$sub" in
  open) cmd_open "$@" ;;
  list) cmd_list "$@" ;;
  close) cmd_close "$@" ;;
  -h|--help|help) usage 0 ;;
  *) usage ;;
esac
