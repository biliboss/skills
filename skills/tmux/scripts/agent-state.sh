#!/usr/bin/env bash
# agent-state.sh: a tab shows when its agent finishes a turn (✓ on bordô) and clears when the owner enters it.
#   agent-state.sh working|done|clear|sub+|sub-|ask|answered [target]   target: pane/window (default: the window of $TMUX_PANE)
#   ask/answered: an open question to the owner (◆ on bordô, @ask) and its answer; Hermes on_human_input_request/resolved
#   agent-state.sh install | uninstall          the tmux cleanup hooks (live + marked block in ~/.tmux.conf)
# Driven by Hermes shell hooks (pre_llm_call -> working, post_llm_call -> done). A hook script must print nothing on
# stdout (Hermes reads it as a directive) and exit fast; working/done/clear are silent and always exit 0.
set -u
TMUX_BIN="${TMUX_BIN:-}"
[ -n "$TMUX_BIN" ] || { [ -x /opt/homebrew/bin/tmux ] && TMUX_BIN=/opt/homebrew/bin/tmux || TMUX_BIN=$(command -v tmux); }
tm() { if [ -n "${TMUX_SOCKET:-}" ]; then "$TMUX_BIN" -L "$TMUX_SOCKET" "$@"; else "$TMUX_BIN" "$@"; fi; }

SLOT=42                                   # indexed hook slot: never clobbers the owner's own set-hook
HOOKS="session-window-changed client-session-changed"
CLEAR='set -w -u window-status-style ; set -w -u window-status-format ; set -w -u @done'
HOOK_CMD="if -F \"#{@done}\" \"$CLEAR\""
BEGIN='# >>> tmux agent-state >>>'; END='# <<< tmux agent-state <<<'
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THREAD_SH="$HERE/../../thread/scripts/thread.sh"
touch_tab() { [ -x "$THREAD_SH" ] && "$THREAD_SH" sort "$1" </dev/null >/dev/null 2>&1; return 0; }   # most recent now; tabs re-sorted (MRU, debounced)

# Hermes shell hooks run in the shared gateway (no $TMUX_PANE) and get JSON on stdin with session_id.
# Window = the one whose @hsid is that id (thread.sh open sets it); else a pane whose process tree mentions the id.
window_of_hook() {
  [ ! -t 0 ] || return 0
  local sid w pid
  sid=$(jq -r '.parent_session_id // .session_id // empty' 2>/dev/null) || return 0   # subagent_start/stop name the PARENT in parent_session_id
  [ -n "$sid" ] || return 0
  w=$(tm list-windows -a -F '#{window_id} #{@hsid}' 2>/dev/null | awk -v s="$sid" '$2==s {print $1; exit}')
  if [ -z "$w" ]; then
    while read -r id pid; do
      [ -n "$pid" ] || continue
      if { ps -o args= -p "$pid"; pgrep -P "$pid" 2>/dev/null | while read -r c; do ps -o args= -p "$c"; done; } 2>/dev/null | grep -qF -- "$sid"; then
        w=$id; break
      fi
    done < <(tm list-panes -a -F '#{window_id} #{pane_pid}' 2>/dev/null)
  fi
  printf '%s' "$w"
}

# Running subagents: @subagents=N on the parent's window (subagent_start +1, subagent_stop -1, never below 0).
# A tab with N>0 shows one grey glyph + N (never bordô: it does not need the owner) and is NOT done: the ✓ waits for 0.
ICON="${AGENT_STATE_ICON:-$(printf '\xef\x80\x93')}"   # Nerd Font cog (U+F013; the owner's Ghostty uses IosevkaTerm Nerd Font); no Nerd Font: AGENT_STATE_ICON='⚙'
subs_of() { local n; n=$(tm display-message -p -t "$1" '#{@subagents}' 2>/dev/null); case $n in ''|*[!0-9]*) n=0 ;; esac; echo "$n"; }
show_subs() { # window, count > 0: grey glyph + count before the name
  tm set-option -w -t "$1" window-status-style 'fg=#8a8a8a' \; set-option -w -t "$1" window-status-format " $ICON$2 #W " >/dev/null 2>&1
}
mark_done() { # window: ✓ bordô when the owner is not on it, else nothing to flag
  local w=$1 info
  info=$(tm display-message -p -t "$w" '#{window_active} #{session_attached}' 2>/dev/null) || return 0
  set -- $info
  tm set-option -w -u -t "$w" @agent >/dev/null 2>&1
  if [ "${1:-0}" = 1 ] && [ "${2:-0}" != 0 ]; then
    tm set-option -w -u -t "$w" window-status-style >/dev/null 2>&1
    tm set-option -w -u -t "$w" window-status-format >/dev/null 2>&1
    tm set-option -w -u -t "$w" @done >/dev/null 2>&1
  else
    tm set-option -w -t "$w" @done 1 \; set-option -w -t "$w" window-status-style 'fg=#ffffff,bg=#800020,bold' \; \
      set-option -w -t "$w" window-status-format ' ✓ #W ' >/dev/null 2>&1
  fi
}

cmd=${1:-}; shift || true
case $cmd in
  working|done|clear|sub+|sub-|ask|answered)
    t=${1:-${TMUX_PANE:-}}
    [ -n "$t" ] || t=$(window_of_hook)    # gateway hook: no $TMUX_PANE, find the window by the session id on stdin
    [ -n "$t" ] || exit 0                 # not inside tmux / no window for it: nothing to mark
    case $cmd in
      ask) tm set-option -w -t "$t" @ask 1 \; set-option -w -t "$t" window-status-style 'fg=#ffffff,bg=#800020,bold' \; \
             set-option -w -t "$t" window-status-format ' ◆ #W ' >/dev/null 2>&1 ;;
      answered) tm set-option -w -u -t "$t" @ask >/dev/null 2>&1
                if [ -z "$(tm display-message -p -t "$t" '#{@done}' 2>/dev/null)" ]; then
                  tm set-option -w -u -t "$t" window-status-style >/dev/null 2>&1; tm set-option -w -u -t "$t" window-status-format >/dev/null 2>&1
                fi ;;
      working) tm set-option -w -t "$t" @agent working >/dev/null 2>&1
               tm set-option -w -u -t "$t" @turnended >/dev/null 2>&1 ;;
      clear) tm set-option -w -u -t "$t" @agent >/dev/null 2>&1
             tm set-option -w -u -t "$t" window-status-style >/dev/null 2>&1
             tm set-option -w -u -t "$t" window-status-format >/dev/null 2>&1
             tm set-option -w -u -t "$t" @done >/dev/null 2>&1
             tm set-option -w -u -t "$t" @ask >/dev/null 2>&1
             tm set-option -w -u -t "$t" @turnended >/dev/null 2>&1 ;;
      done)
        w=$(tm display-message -p -t "$t" '#{window_id}' 2>/dev/null) || exit 0; [ -n "$w" ] || exit 0
        n=$(subs_of "$w")
        if [ "$n" -gt 0 ]; then        # subagents still running: not done yet, the ✓ comes when the count reaches 0
          tm set-option -w -t "$w" @turnended 1 >/dev/null 2>&1; show_subs "$w" "$n"
        else mark_done "$w"; fi ;;
      sub+) w=$(tm display-message -p -t "$t" '#{window_id}' 2>/dev/null) || exit 0; [ -n "$w" ] || exit 0
            n=$(( $(subs_of "$w") + 1 ))
            tm set-option -w -t "$w" @subagents "$n" >/dev/null 2>&1; show_subs "$w" "$n" ;;
      sub-) w=$(tm display-message -p -t "$t" '#{window_id}' 2>/dev/null) || exit 0; [ -n "$w" ] || exit 0
            n=$(subs_of "$w"); [ "$n" -gt 0 ] || exit 0   # nothing running: never below 0, leave the tab as it is
            n=$((n - 1))
            if [ "$n" -gt 0 ]; then tm set-option -w -t "$w" @subagents "$n" >/dev/null 2>&1; show_subs "$w" "$n"
            else
              tm set-option -w -u -t "$w" @subagents >/dev/null 2>&1
              tm set-option -w -u -t "$w" window-status-style >/dev/null 2>&1
              tm set-option -w -u -t "$w" window-status-format >/dev/null 2>&1
              if [ -n "$(tm display-message -p -t "$w" '#{@turnended}' 2>/dev/null)" ]; then   # the parent's turn already ended: ✓ now
                tm set-option -w -u -t "$w" @turnended >/dev/null 2>&1; mark_done "$w"
              fi
            fi ;;
    esac
    [ "$cmd" = clear ] || touch_tab "$t"   # prompt arrived / turn ended: this thread is now the most recent
    exit 0 ;;
  install|uninstall)
    conf=${TMUX_CONF:-$HOME/.tmux.conf}
    [ -f "$conf" ] && body=$(awk -v b="$BEGIN" -v e="$END" '$0==b{s=1;next} $0==e{s=0;next} !s' "$conf") || body=""
    if [ "$cmd" = install ]; then
      { [ -z "$body" ] || printf '%s\n\n' "$body"; printf '%s\n' "$BEGIN"
        for h in $HOOKS; do printf "set-hook -g %s[%s] '%s'\n" "$h" "$SLOT" "$HOOK_CMD"; done
        printf '%s\n' "$END"; } > "$conf.tmp" && mv "$conf.tmp" "$conf"
      for h in $HOOKS; do tm set-hook -g "${h}[$SLOT]" "$HOOK_CMD" 2>/dev/null; done
      echo "hooks in $conf and live ($HOOKS)"
      cat <<EOF
Hermes side (profile bili): config.yaml hooks, then approve both pairs in shell-hooks-allowlist.json:
hooks:
  pre_llm_call:
    - command: "$HERE/agent-state.sh working"
  post_llm_call:
    - command: "$HERE/agent-state.sh done"
  subagent_start:
    - command: "$HERE/agent-state.sh sub+"
  subagent_stop:
    - command: "$HERE/agent-state.sh sub-"
  on_human_input_request:
    - command: "$HERE/agent-state.sh ask"
  on_human_input_resolved:
    - command: "$HERE/agent-state.sh answered"
EOF
    else
      [ ! -f "$conf" ] || { printf '%s\n' "$body" > "$conf.tmp" && mv "$conf.tmp" "$conf"; }
      for h in $HOOKS; do tm set-hook -gu "${h}[$SLOT]" 2>/dev/null; done
      echo "hooks removed"
    fi ;;
  *) echo "usage: agent-state.sh working|done|clear|sub+|sub-|ask|answered [target] | install | uninstall" >&2; exit 2 ;;
esac
