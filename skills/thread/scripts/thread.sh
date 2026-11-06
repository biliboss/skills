#!/usr/bin/env bash
# thread.sh: open/list/close a topic thread (a tmux window running a Hermes session) in the session where you are, in one call.
#   thread.sh open <topic> [--card C] [--session S] [--from SESSION_ID | --new] [--profile P] [--cwd DIR] [--brief TEXT | --brief - | --brief-gz B64] [--no-shape]
#   thread.sh list
#   thread.sh close <topic> [--session S] [--summary TEXT] [--by owner|bili]   |   close --self [--summary TEXT]
#   (the owner is on that tab: it closes when he leaves; each close writes a line to $THREAD_LOG, default ~/.local/state/threads.log)
#   thread.sh state [<tab>] | watch   the threads' state as JSON lines (●◆✓/idle, subagents, card); watch = live from NATS
#   thread.sh doctor [--json] [--verbose] [--profile P]   read-only drift check of the thread invariant (exit 0 ok, 1 drift, 2 cannot run)
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
usage() { sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-2}"; }

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
  tm list-windows -t "=$1" -F '#{window_id}|#{@thread}' 2>/dev/null | awk -F'|' -v t="$2" '$2==t {print $1; exit}'  # names may hold spaces
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

# The Value Object `thread`: ONE name for a thread, used as is everywhere (tmux session, its tab, @thread, the Hermes
# session title). Lowercase ASCII; spaces and - stay, a dot becomes -: "Sygnal 0.2" -> "sygnal 0-2", "Ação Já!" -> "acao ja".
# NEVER a dot: tmux reads "a.b" in a target as window.pane, so has-session/switch-client (sesh, the owner's shortcuts) cannot reach it.
# Spaces are safe: `tmux has-session -t 'a b'` works (checked on a private server).
thread() { # raw text -> the thread name (empty when nothing is left)
  printf '%s' "$1" | perl -CS -MUnicode::Normalize -pe '$_ = lc NFD($_); s/\pM//g' |
    sed -E 's/\./-/g; s/[^a-z0-9 -]+/ /g; s/ +/ /g; s/^ //; s/ $//'
}

cmd_open() {
  [ $# -ge 1 ] || usage
  local topic; topic="$(thread "$1")"; shift
  [ -n "$topic" ] || die "the thread name is empty after normalizing (use letters or digits)"
  local mode="" from="" card="" session="" PROFILE="bili" cwd="$PWD" brief="" have_brief=0 shape=1
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
      --no-shape) shape=0 ;;
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
  # -d: the thread opens in the BACKGROUND. Never select-window/switch-client: the owner's focus is not ours to move.
  if [ "${THREAD_TAB:-0}" = 1 ]; then  # legacy: a tab right after the invoking agent's window
    win="$(tm new-window -a -d -P -F '#{window_id}' -t "$after" -n "$topic" -c "$cwd" "$hcmd")"
  else  # the owner's rule: every thread is its own tmux session, the thread as its 1st tab
    tm has-session -t "=$topic" 2>/dev/null && die "a tmux session '$topic' already exists (pick another topic)"
    win="$(tm new-session -d -P -F '#{window_id}' -s "$topic" -n "$topic" -c "$cwd" "$hcmd")"
    tm set-option -t "=$topic:" @parent "$session" 2>/dev/null || true
  fi
  tm set-option -w -t "$win" @thread "$topic"
  [ -z "$kid" ] || tm set-option -w -t "$win" @card "$kid"
  [ -z "$newid" ] || tm set-option -w -t "$win" @hsid "$newid"   # agent-state.sh finds the window by it (hooks have no $TMUX_PANE)

  wait_ready "$win" || die "Hermes did not get ready in ${READY_TIMEOUT}s (window $win left open)"

  local sid="$newid"
  if [ "$have_brief" = 1 ] && [ -n "$brief" ]; then
    # a thread starts in shape (the owner's rule: the system must experiment); skipped when the brief already mentions shape or --no-shape
    if [ "$shape" = 1 ] && ! printf '%s' "$brief" | grep -qi shape; then
      brief="Comece pela skill shape (skill_view shape): abrir esta thread já é começar um shape deste contexto; registre com shape.sh emit request.received --shaping $topic."$'\n'"$brief"
    fi
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
    # no -d: on tmux 3.7, swap-window -d makes the moved window current (it stole the owner's focus); without it the
    # focus stays where it was
    tm swap-window -s "$w" -t "${cur[k]}" 2>/dev/null || break
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
  # indexes changed: the session's lines, live (only when something moved would be nicer; one message per thread is cheap)
  state_lines -t "=$sess" | publish
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
      *) [ -z "$topic" ] || die "unexpected argument: $1"; topic="$(thread "$1")" ;;
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

# --- doctor: READ-ONLY check of the thread invariant (never kills, renames, moves or selects anything)
# Every thread (a window with @thread) has (a) its own tmux session named like the thread, as that session's window, and
# (b) a live Hermes session: @hsid set, present in the profile's state.db, not ended, and the pane resumes THAT id.
# Also: a tmux session whose windows carry @card but no @thread (a card is never a session of its own).
cmd_doctor() {
  # Protocol of the `doctor` skill: one finding = dimension, check, status, evidence, action (the action is NEVER run here).
  # Text: <status> <dimension> <check> <session>/<window-id>: <evidence> -> <action>.  Exit 0 healthy, 1 drift/fail, 2 cannot run.
  local json=0 verbose=0 PROFILE="bili" db="" have_db=1 n=0 bad=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --json) json=1 ;;
      --verbose) verbose=1 ;;
      --profile) PROFILE="${2:?}"; shift ;;
      *) echo "thread.sh doctor: unknown option: $1" >&2; return 2 ;;
    esac
    shift
  done
  tm list-sessions >/dev/null 2>&1 || { echo "thread.sh doctor: no tmux server to check" >&2; return 2; }
  db="${THREAD_STATE_DB:-$HOME/.hermes/profiles/$PROFILE/state.db}"
  local sq; sq="$(type -P sqlite3 || true)"
  jesc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
  finding() { # status dimension check session window evidence action
    local st="$1" dim="$2" chk="$3" s="$4" wid="$5" ev="$6" act="$7"
    [ "$st" != ok ] || [ "$verbose" = 1 ] || return 0
    case "$st" in drift|fail) bad=$((bad + 1)) ;; esac
    if [ "$json" = 1 ]; then
      printf '{"dimension":"%s","check":"%s","status":"%s","session":"%s","window":"%s","evidence":"%s","action":"%s"}\n' \
        "$dim" "$chk" "$st" "$(jesc "$s")" "$wid" "$(jesc "$ev")" "$(jesc "$act")"
    else printf '%s %s %s %s/%s: %s -> %s\n' "$st" "$dim" "$chk" "$s" "$wid" "$ev" "$act"; fi
  }
  if [ -z "$sq" ] || [ ! -f "$db" ]; then
    have_db=0
    finding warn environment state-db - - "$db missing or no sqlite3" "install sqlite3 / pass --profile P for a profile that has a state.db; Hermes checks skipped"
  fi
  local sess wid th hsid card cmd row expect bad0 reopen
  while IFS='|' read -r sess wid th hsid card cmd; do
    [ -n "$th" ] || continue
    n=$((n + 1))
    reopen="thread.sh close '$th' --session '$sess'; thread.sh open '$th' --from <live Hermes session id>"
    expect="$(printf '%s' "$th" | tr '.:' '__')"
    if [ "$sess" != "$th" ] && [ "$sess" != "$expect" ]; then
      finding drift environment thread-has-own-session "$sess" "$wid" "thread '$th' lives in tmux session '$sess'" "tmux rename-session -t '=$sess' '$th'  (or $reopen)"
    elif [ "$(tm list-windows -t "=$sess" 2>/dev/null | grep -c .)" -gt 1 ]; then
      finding warn environment thread-has-own-session "$sess" "$wid" "session '$sess' has more than the thread's own window" "tmux move-window -s <other window> -t <its own session>:"
    else finding ok environment thread-has-own-session "$sess" "$wid" "session '$sess' holds thread '$th'" "-"; fi

    if [ -z "$hsid" ]; then
      finding drift observability hsid-set "$sess" "$wid" "no @hsid: hooks cannot find the tab, so no light and no sort" "tmux set-option -w -t $wid @hsid <Hermes session id the pane resumes>"
    else
      case "$hsid" in
        *[!A-Za-z0-9_.-]*) finding drift observability hsid-set "$sess" "$wid" "@hsid '$hsid' is not an id" "tmux set-option -w -t $wid @hsid <Hermes session id>"; hsid="" ;;
        *) finding ok observability hsid-set "$sess" "$wid" "@hsid $hsid" "-" ;;
      esac
    fi
    if [ -n "$hsid" ] && [ "$have_db" = 1 ]; then
      row="$("$sq" -readonly "$db" "select ended_at is not null from sessions where id='$hsid'" 2>/dev/null || true)"
      if [ -z "$row" ]; then finding drift environment hsid-in-db "$sess" "$wid" "@hsid $hsid is not in the $PROFILE state.db" "$reopen"
      else finding ok environment hsid-in-db "$sess" "$wid" "@hsid $hsid is in the $PROFILE state.db" "-"
        if [ "$row" != 0 ]; then finding drift behavior hsid-live "$sess" "$wid" "@hsid $hsid is an ended Hermes session (ended_at set)" "$reopen"
        else finding ok behavior hsid-live "$sess" "$wid" "@hsid $hsid not ended" "-"; fi
      fi
    fi
    bad0=$bad
    case "$cmd" in
      *--continue*) finding drift environment resume-hsid "$sess" "$wid" "start command: $cmd" "tmux respawn-pane -k -t $wid \"hermes -p $PROFILE --resume ${hsid:-<hsid>}\"  (--continue makes a second client of another chat)" ;;
      *"--resume $hsid"*|*"threadview.py $hsid"*) [ -n "$hsid" ] || finding drift environment resume-hsid "$sess" "$wid" "start command resumes an id but there is no @hsid: $cmd" "tmux set-option -w -t $wid @hsid <that id>" ;;
      *) [ -z "$hsid" ] || finding drift environment resume-hsid "$sess" "$wid" "start command does not resume @hsid $hsid: $cmd" "tmux respawn-pane -k -t $wid \"hermes -p $PROFILE --resume $hsid\"" ;;
    esac
    [ "$bad" != "$bad0" ] || [ -z "$hsid" ] || finding ok environment resume-hsid "$sess" "$wid" "start command resumes $hsid" "-"
    case "$cmd" in
      *threadview.py*) local vp vd; vp="$(printf '%s' "$cmd" | grep -o '[^ ]*threadview\.py' | head -1)"; vd="$(dirname "$vp")"
        [ "$vd" = "$HERE" ] || finding warn environment viewer-path "$sess" "$wid" "pane runs threadview.py from $vd, not $HERE" "tmux respawn-pane -k -t $wid with the threadview.py of the checkout you ship" ;;
    esac
  done < <(tm list-windows -a -F '#{session_name}|#{window_id}|#{@thread}|#{@hsid}|#{@card}|#{pane_start_command}' 2>/dev/null)
  local s
  while IFS='|' read -r s wid; do
    finding drift architecture card-not-a-session "$s" "$wid" "session carries @card but no @thread" "make it a thread (thread.sh open '$s' --card <card> --from <id>) or a tab: tmux move-window -s $wid -t <parent session>:"
  done < <(tm list-windows -a -F '#{session_name}|#{window_id}|#{@thread}|#{@card}' 2>/dev/null |
    awk -F'|' '{ if ($3 != "") th[$1]=1; else if ($4 != "" && !($1 in first)) first[$1]=$2 } END { for (s in first) if (!(s in th)) print s "|" first[s] }' | sort)
  # name-targetable: a dot in a session/window name is read by tmux as window.pane, so no target (sesh, switch-client) reaches it.
  local sid wn fix seen=" "
  while IFS='|' read -r s sid wid wn; do
    case "$s" in
      *.*) case "$seen" in *" $sid "*) ;; *) seen="$seen$sid "
        fix="$(thread "$s")"; [ -n "$fix" ] || fix="renamed"
        finding drift environment name-targetable "$s" "$wid" "name '$s' has a dot; tmux reads it as window.pane, so sesh/switch-client cannot reach it" "tmux rename-session -t '$sid' '$fix'" ;; esac ;;
    esac
    case "$wn" in
      *.*) fix="$(thread "$wn")"; [ -n "$fix" ] || fix="renamed"
        finding drift environment name-targetable "$s" "$wid" "name '$wn' has a dot; tmux reads it as window.pane, so sesh/switch-client cannot reach it" "tmux rename-window -t '$wid' '$fix'" ;;
    esac
  done < <(tm list-windows -a -F '#{session_name}|#{session_id}|#{window_id}|#{window_name}' 2>/dev/null)
  if [ "$json" = 0 ]; then
    if [ "$bad" -eq 0 ]; then echo "ok $n threads"; else echo "drift $bad of $n"; fi
  fi
  [ "$bad" -eq 0 ]
}

# --- realtime state (thread-state.sh: the hot path, event on write; see its header for why not tmux -C)
. "$HERE/thread-state.sh"
NATS_BIN="${NATS_BIN:-$(type -P nats || echo "$HOME/.local/bin/nats")}"

cmd_state() { # [<target>]: the target's window, else every thread in every session
  if [ $# -gt 0 ]; then state_of "$1"; else state_lines -a; fi
}

cmd_publish() { # <target> [--session]: publish the target's line (or its whole session's)
  "$HERE/thread-state.sh" pub "$@"
}

cmd_watch() { # the current state first, then one line per change, live from NATS
  cmd_state
  [ -x "$NATS_BIN" ] || die "watch: nats CLI not found (NATS_BIN); no live source"
  "$NATS_BIN" -s "$THREAD_NATS_URL" rtt >/dev/null 2>&1 || die "watch: NATS at $THREAD_NATS_URL is down; no live source"
  exec "$NATS_BIN" -s "$THREAD_NATS_URL" sub --raw "$THREAD_SUBJECT" 2>/dev/null
}

[ $# -gt 0 ] || usage
case "$1" in
  state) shift; cmd_state "$@" ;;
  publish) shift; cmd_publish "$@" ;;
  watch) shift; cmd_watch "$@" ;;
  doctor) shift; cmd_doctor "$@" ;;
  open) shift; cmd_open "$@" ;;
  list) shift; cmd_list "$@" ;;
  close) shift; cmd_close "$@" ;;
  touch) shift; cmd_touch "$@"; cmd_sweep ;;
  sort) shift; cmd_sort "$@"; cmd_sweep ;;
  sweep) shift; cmd_sweep ;;
  -h|--help|help) usage 0 ;;
  *) usage ;;
esac
