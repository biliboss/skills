#!/usr/bin/env bash
# thread.sh: open/list/close a topic thread (a tmux window running a Hermes session) in the session where you are, in one call.
#   thread.sh open <topic> [--card C] [--session S] [--from SESSION_ID | --new] [--profile P] [--cwd DIR] [--brief TEXT | --brief - | --brief-gz B64]
#   thread.sh list
#   thread.sh close <topic> [--session S] [--summary TEXT] [--by owner|bili]   |   close --self [--summary TEXT]
#   (the owner is on that tab: it closes when he leaves; each close writes a line to $THREAD_LOG, default ~/.local/state/threads.log)
#   thread.sh sweep            closes the tabs marked done-and-closing that the owner left
#   thread.sh sort [<tab>] [--now]   stamp <tab> as most recent, re-sort its session's tabs (MRU with an attention band;
#                              debounced ~2 s, THREAD_SORT_DEBOUNCE); the owner's tab never moves. touch <tab> = sort <tab> --now
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
usage() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-2}"; }

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
  # -d: the window opens in the BACKGROUND. Never select-window/switch-client: the owner's focus is not ours to move.
  win="$(tm new-window -a -d -P -F '#{window_id}' -t "$after" -n "$topic" -c "$cwd" "$hcmd")"
  tm set-option -w -t "$win" @thread "$topic"
  [ -z "$kid" ] || tm set-option -w -t "$win" @card "$kid"
  [ -z "$newid" ] || tm set-option -w -t "$win" @hsid "$newid"   # agent-state.sh finds the window by it (hooks have no $TMUX_PANE)

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
  [ -z "$sid" ] || tm set-option -w -t "$win" @hsid "$sid"
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

# --- tab order: an MRU list (most recently used first, like macOS's ⌘Tab) with an attention band in front ---
# Tab 1 = the session's first window (the Bili); windows without @thread (zsh…) last, in their own order. Threads between,
# by band then MRU: 0 = needs the owner (@ask ◆ open question, @done ✓ finished and not seen), 1 = working (@agent or
# @subagents), 2 = idle and seen; inside a band the highest @touched (ms) first, ties keep the current order.
# The window the owner is on never moves (it keeps its index; the others are arranged around it) and keeps the focus.
now_ms() { perl -MTime::HiRes=time -e 'printf "%d", time()*1000' 2>/dev/null || printf '%s000' "$(date +%s)"; }

desired_order() { # session -> window ids, one per line, in the order the rules want (active window pinned in place)
  local sess="$1" line id act th ask done ag subs tch pos=0 first="" active="" apos=0 band others="" keys="" d=() out=() i
  while IFS='|' read -r id act th ask done ag subs tch; do
    [ -n "$id" ] || continue
    [ "$act" = 1 ] && { active="$id"; apos=$pos; }
    if [ "$pos" = 0 ]; then first="$id"
    elif [ -n "$th" ]; then
      band=2
      case "$subs" in ''|0|*[!0-9]*) ;; *) band=1 ;; esac
      [ "$ag" != working ] || band=1
      [ -z "$ask$done" ] || band=0
      case "$tch" in ''|*[!0-9]*) tch=0 ;; esac
      keys="$keys$(printf '%d %015d %04d %s' "$band" "$((999999999999999 - tch))" "$pos" "$id")"$'\n'
    else others="$others$id"$'\n'; fi
    pos=$((pos + 1))
  done < <(tm list-windows -t "=$sess" -F '#{window_id}|#{window_active}|#{@thread}|#{@ask}|#{@done}|#{@agent}|#{@subagents}|#{@touched}' 2>/dev/null)
  [ -n "$first" ] || return 0
  while IFS= read -r line; do [ -z "$line" ] || d[${#d[@]}]="$line"; done \
    < <(printf '%s\n' "$first"; printf '%s' "$keys" | sort | awk 'NF {print $4}'; printf '%s' "$others")
  # pin the owner's window at its current index
  for ((i = 0; i < ${#d[@]}; i++)); do [ "${d[i]}" = "$active" ] || out[${#out[@]}]="${d[i]}"; done
  if [ -n "$active" ]; then
    d=(); for ((i = 0; i < ${#out[@]}; i++)); do [ "$i" != "$apos" ] || d[${#d[@]}]="$active"; d[${#d[@]}]="${out[i]}"; done
    [ "$apos" -lt "${#out[@]}" ] || d[${#d[@]}]="$active"
  else d=("${out[@]}"); fi
  printf '%s\n' "${d[@]}"
}

# Motion: a tab that changes place slides there one step at a time (swap-window with its neighbour, $THREAD_ANIM_MS
# per step, default 45; 0 = jump) and glows burgundy while it moves, fading back ~0.6 s after it lands. The owner's
# window is never swapped: when it stands in the path, the tab jumps over it in one move.
slide() { # window target-index active-window current-order...
  local w="$1" to="$2" active="$3"; shift 3
  local cur=("$@") j=-1 k ms="${THREAD_ANIM_MS:-45}" blocked=0
  for ((k = 0; k < ${#cur[@]}; k++)); do [ "${cur[k]}" != "$w" ] || j=$k; done
  for ((k = to; k < j; k++)); do [ "${cur[k]}" != "$active" ] || blocked=1; done
  if [ "$ms" = 0 ] || [ "$j" -le "$to" ] || [ "$blocked" = 1 ]; then
    tm move-window -d -b -s "$w" -t "${cur[to]}" 2>/dev/null || true
    return 0
  fi
  local step; step="$(awk -v m="$ms" 'BEGIN { printf "%.3f", m / 1000 }')"
  tm set-option -w -t "$w" window-status-style 'fg=#800020,bold' 2>/dev/null || true
  for ((k = j - 1; k >= to; k--)); do
    tm swap-window -d -s "$w" -t "${cur[k]}" 2>/dev/null || break
    sleep "$step"
  done
  ( sleep 0.6; tm set-option -w -u -t "$w" window-status-style 2>/dev/null ) </dev/null >/dev/null 2>&1 &
  return 0
}

sort_session() { # session: move only what is out of place (move-window -d keeps the focus), then renumber 1..N
  local sess="$1" want=() cur=() i j k line
  while IFS= read -r line; do [ -z "$line" ] || want[${#want[@]}]="$line"; done < <(desired_order "$sess")
  [ "${#want[@]}" -gt 0 ] || return 0
  local active; active="$(tm list-windows -t "=$sess" -F '#{window_active} #{window_id}' 2>/dev/null | awk '$1==1 {print $2}')"
  for ((i = 0; i < ${#want[@]}; i++)); do
    cur=(); while IFS= read -r line; do cur[${#cur[@]}]="$line"; done < <(tm list-windows -t "=$sess" -F '#{window_id}' 2>/dev/null)
    [ "${cur[i]:-}" != "${want[i]}" ] || continue
    if [ "${want[i]}" = "$active" ]; then   # never move the owner's window: the ones before it go behind it
      j=-1; for ((k = 0; k < ${#cur[@]}; k++)); do [ "${cur[k]}" != "$active" ] || j=$k; done
      for ((k = j - 1; k >= i; k--)); do tm move-window -d -a -s "${cur[k]}" -t "$active" 2>/dev/null || true; done
    else
      slide "${want[i]}" "$i" "$active" "${cur[@]}"
    fi
  done
  # -a/-b shift indexes up and renumber-windows only acts on close: close the gaps now (tabs stay 1..N)
  tm move-window -r -t "=$sess" 2>/dev/null || true
}

cmd_sort() { # [<target>] [--now]: stamp the target thread's @touched, then re-sort its session (debounced ~2 s)
  local target="" now=0 info sess th wid token deb="${THREAD_SORT_DEBOUNCE:-2}"
  while [ $# -gt 0 ]; do case "$1" in --now) now=1 ;; *) target="$1" ;; esac; shift; done
  if [ -n "$target" ]; then
    info="$(tm display-message -p -t "$target" '#{session_name}|#{window_id}|#{@thread}' 2>/dev/null)" || return 0
    sess="${info%%|*}"; info="${info#*|}"; wid="${info%%|*}"; th="${info#*|}"
    [ -z "$th" ] || tm set-option -w -t "$wid" @touched "$(now_ms)" 2>/dev/null || true
  else sess="$(target_session "")"; fi
  if [ "$now" = 1 ] || [ "$deb" = 0 ]; then sort_session "$sess"; return 0; fi
  # debounce: the last request in a quiet window of $deb seconds wins, so tabs do not jump on every event
  token="$(now_ms)$$"; tm set-option -t "=$sess:" @sortreq "$token" 2>/dev/null || true
  ( sleep "$deb"
    if [ "$(tm show-options -qv -t "=$sess:" @sortreq 2>/dev/null)" = "$token" ]; then sort_session "$sess"; cmd_sweep; fi
  ) </dev/null >/dev/null 2>&1 &
  return 0
}

cmd_touch() { # <tab>: compatibility name: stamp it and sort now
  [ $# -eq 1 ] || usage
  cmd_sort "$1" --now
}

THREAD_LOG="${THREAD_LOG:-$HOME/.local/state/threads.log}"
SWEEP_SLOT=72

log_close() { # window id -> one line: when, topic, card, session id, summary, by (tab-separated)
  local wid="$1" sum="$2" by="$3" topic card sid
  topic="$(tm display-message -p -t "$wid" '#{@thread}')"; card="$(tm display-message -p -t "$wid" '#{@card}')"
  sid="$(tm display-message -p -t "$wid" '#{@hsid}')"
  mkdir -p "$(dirname "$THREAD_LOG")"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$topic" "${card:--}" "${sid:--}" "$(printf '%s' "$sum" | tr '\t\n' '  ')" "$by" >>"$THREAD_LOG"
}

do_close() { # window id, summary, by. The owner is on this tab: mark it and close it when he leaves (never move his focus).
  local wid="$1" sum="$2" by="$3"
  if [ "$(tm display-message -p -t "$wid" '#{window_active}')" = 1 ]; then
    tm set-option -w -t "$wid" @closing "$by" \; set-option -w -t "$wid" @closesum "$sum"
    tm set-hook -g "session-window-changed[$SWEEP_SLOT]" "run-shell -b '$HERE/thread.sh sweep'"
    echo "deferred: the owner is on this tab; it closes when he leaves it"
    return 0
  fi
  log_close "$wid" "$sum" "$by"
  tm kill-window -t "$wid"
}

cmd_sweep() { # close the windows marked @closing that the owner is no longer on; drop the hook when none is left
  local wid active by sum left=0
  while IFS='|' read -r wid active by; do
    [ -n "$by" ] || continue
    if [ "$active" = 1 ]; then left=$((left + 1)); continue; fi
    sum="$(tm display-message -p -t "$wid" '#{@closesum}')"
    log_close "$wid" "$sum" "$by"; tm kill-window -t "$wid" 2>/dev/null || true
  done < <(tm list-windows -a -F '#{window_id}|#{window_active}|#{@closing}' 2>/dev/null)
  [ "$left" -gt 0 ] || tm set-hook -gu "session-window-changed[$SWEEP_SLOT]" 2>/dev/null || true
}

cmd_close() {
  local topic="" session="" hits n self=0 sum="" by="" wid="" w
  while [ $# -gt 0 ]; do
    case "$1" in
      --session) session="${2:?}"; shift ;;
      --self) self=1 ;;
      --summary) sum="${2:?}"; shift ;;
      --by) by="${2:?}"; shift ;;
      -*) die "unknown option: $1" ;;
      *) [ -z "$topic" ] || die "unexpected argument: $1"; topic="$1" ;;
    esac
    shift
  done
  if [ "$self" = 1 ]; then # the window whose @hsid is this session, else the window of $TMUX_PANE
    [ -z "${HERMES_SESSION_ID:-}" ] || wid="$(tm list-windows -a -F '#{window_id} #{@hsid}' 2>/dev/null | awk -v s="$HERMES_SESSION_ID" '$2==s {print $1; exit}')"
    [ -n "$wid" ] || [ -z "${TMUX_PANE:-}" ] || wid="$(tm display-message -p -t "$TMUX_PANE" '#{window_id}' 2>/dev/null || true)"
    [ -n "$wid" ] || die "close --self: no window with @hsid=${HERMES_SESSION_ID:-<unset>} and not inside tmux"
    [ -n "$(tm display-message -p -t "$wid" '#{@thread}')" ] || die "close --self: that window is not a thread"
    topic="$(tm display-message -p -t "$wid" '#{@thread}')"; by="${by:-self}"
    n="$(tm display-message -p -t "$wid" '#{@subagents}')"
    case "$n" in ''|0) ;; *) die "close --self: $n subagent(s) still running; not done yet (close when the count is 0)" ;; esac
    do_close "$wid" "$sum" "$by"
    [ "$(tm display-message -p -t "$wid" '#{@closing}' 2>/dev/null)" ] || echo "closed $topic (the Hermes session stays)"
    return 0
  fi
  [ -n "$topic" ] || usage
  by="${by:-owner}"
  if [ -n "$session" ]; then hits="$(find_window "$session" "$topic" | sed "s|^|$session\t|")"
  else hits="$(cmd_list | awk -F'\t' -v t="$topic" '$2==t {print $1 "\t" $3}')"; fi
  n="$(printf '%s' "$hits" | grep -c . || true)"
  [ "$n" -ge 1 ] || die "no thread '$topic'"
  [ "$n" -eq 1 ] || die "thread '$topic' is open in more than one session; pass --session S"
  w="$(printf '%s' "$hits" | cut -f2)"
  do_close "$w" "$sum" "$by"
  [ -n "$(tm display-message -p -t "$w" '#{@closing}' 2>/dev/null)" ] || echo "closed $topic in $(printf '%s' "$hits" | cut -f1) (the Hermes session stays)"
}

[ $# -gt 0 ] || usage
case "$1" in
  open) shift; cmd_open "$@" ;;
  list) shift; cmd_list "$@" ;;
  close) shift; cmd_close "$@" ;;
  touch) shift; cmd_touch "$@"; cmd_sweep ;;
  sort) shift; cmd_sort "$@"; cmd_sweep ;;
  sweep) shift; cmd_sweep ;;
  -h|--help|help) usage 0 ;;
  *) usage ;;
esac
