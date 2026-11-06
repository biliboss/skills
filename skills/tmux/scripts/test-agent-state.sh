#!/usr/bin/env bash
# test-agent-state.sh: agent-state.sh on a PRIVATE tmux server (-L). Never touches the owner's server or ~/.tmux.conf.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
unset TMUX TMUX_PANE
export TMUX_SOCKET="agentstate-$$" TMUX_BIN="${TMUX_BIN:-/opt/homebrew/bin/tmux}"
[ -x "$TMUX_BIN" ] || TMUX_BIN=$(command -v tmux); export TMUX_BIN
export TMUX_CONF; TMUX_CONF=$(mktemp "${TMPDIR:-/tmp}/agent-state-conf.XXXXXX")
AS="$HERE/agent-state.sh"
tm() { "$TMUX_BIN" -L "$TMUX_SOCKET" "$@"; }
cleanup() { tm kill-server >/dev/null 2>&1; rm -f "$TMUX_CONF" "$TMUX_CONF.tmp"; kill "$CLIENT" 2>/dev/null; }
trap cleanup EXIT
pass=0; failn=0
t() { if [ "$2" = "$3" ]; then printf 'ok    %s\n' "$1"; pass=$((pass+1)); else printf 'FAIL  %s (got [%s], want [%s])\n' "$1" "$2" "$3"; failn=$((failn+1)); fi; }
opt() { tm show-options -wqv -t "$1" "$2"; }

tm -f /dev/null new-session -d -s s -n active -x 100 -y 30 'sleep 600' || { echo "no server"; exit 1; }
tm new-window -d -t s -n bg 'sleep 600'
FIFO="$TMUX_CONF.fifo"; mkfifo "$FIFO"
tm -C attach -t s <"$FIFO" >/dev/null 2>&1 & CLIENT=$!   # an attached (control) client; fd 9 holds its stdin open
exec 9>"$FIFO"
until [ "$(tm display-message -p -t s '#{session_attached}')" != 0 ]; do :; done
PA=$(tm display-message -p -t s:active '#{pane_id}'); PB=$(tm display-message -p -t s:bg '#{pane_id}')

"$AS" install >/dev/null
"$AS" install >/dev/null
t "install: one slot per hook (idempotent, live)" "$(tm show-hooks -g | grep -c '\[42\]')" 2
t "install: one marked block in the conf" "$(grep -c '>>> tmux agent-state' "$TMUX_CONF")" 1

out=$(TMUX_PANE=$PB "$AS" working); t "working prints nothing" "$out" ""
t "working sets @agent" "$(opt s:bg @agent)" working
out=$(TMUX_PANE=$PB "$AS" done); t "done prints nothing" "$out" ""
t "done on a background window: @done=1" "$(opt s:bg @done)" 1
t "done: style" "$(opt s:bg window-status-style)" 'fg=#ffffff,bg=#800020,bold'
t "done: format" "$(opt s:bg window-status-format)" ' ✓ #W '
t "done clears @agent" "$(opt s:bg @agent)" ""
t "done on the window the owner is on: no mark" "$(TMUX_PANE=$PA "$AS" done; opt s:active @done)" ""
t "no TMUX_PANE: silent exit 0" "$("$AS" done; echo $?)" 0

tm select-window -t s:bg                                  # the owner enters the marked tab
t "entering the tab clears @done (hook)" "$(opt s:bg @done)" ""
t "entering the tab restores the style" "$(opt s:bg window-status-style)" ""
t "entering the tab restores the format" "$(opt s:bg window-status-format)" ""

tm select-window -t s:active; TMUX_PANE=$PB "$AS" done
"$AS" clear "$PB"; t "clear unsets everything" "$(opt s:bg @done)$(opt s:bg window-status-style)" ""

"$AS" uninstall >/dev/null
t "uninstall: hooks gone" "$(tm show-hooks -g | grep -c '\[42\]')" 0
t "uninstall: block gone" "$(grep -c 'agent-state' "$TMUX_CONF")" 0

# --- recency order: Bili = tab 1, threads newest first from tab 2, non-threads last, focus never moves ---
tm new-session -d -s o -n bili -x 100 -y 30 'sleep 600'
for n in a b c; do tm new-window -d -t o -n "$n" 'sleep 600'; tm set-option -w -t "o:$n" @thread "$n"; done
tm new-window -d -t o -n z 'sleep 600'
tm select-window -t o:c                                  # the owner is on c
order() { tm list-windows -t o -F '#{window_name}' | tr '\n' ' '; }
act() { tm list-windows -t o -F '#{window_name}#{window_active}' | grep -E '1$' | tr -d '\n'; }
pane() { tm display-message -p -t "o:$1" '#{pane_id}'; }
t "order: start" "$(order)" "bili a b c z "
TMUX_PANE=$(pane b) "$AS" working
t "prompt in b: b jumps to tab 2, a shifts" "$(order)" "bili b a c z "
t "focus stayed on c" "$(act)" c1
TMUX_PANE=$(pane a) "$AS" done
t "end of a's turn: a jumps to tab 2 again" "$(order)" "bili a b c z "
t "focus still on c" "$(act)" c1
TMUX_PANE=$(pane z) "$AS" working
t "non-thread window stays last" "$(order)" "bili a b c z "
TMUX_PANE=$(pane c) "$AS" working
t "the focused thread moves too, and keeps the focus" "$(order)$(act)" "bili c a b z c1"
TMUX_PANE=$(pane bili) "$AS" working
t "the Bili stays tab 1" "$(order)" "bili c a b z "
"$HERE/../../thread/scripts/thread.sh" touch "$(pane b)"
t "thread.sh touch <tab> alone" "$(order)" "bili b c a z "

# running subagents: the hook payload names the PARENT in parent_session_id; count on @hsid's window
tm new-window -d -t s -n sub 'sleep 600'; tm set-option -w -t s:sub @hsid parent-1; tm set-option -w -t s:sub @thread sub
hk() { printf '{"parent_session_id":"parent-1","child_session_id":"kid-%s"}' "$RANDOM" | "$AS" "$1"; }
hk sub+; hk sub+
t "subagent_start x2: @subagents=2" "$(opt s:sub @subagents)" 2
t "tab shows the glyph and the count, grey" "$(opt s:sub window-status-format)|$(opt s:sub window-status-style)" " $(printf '\xef\x80\x93')2 #W |fg=#8a8a8a"
TMUX_PANE=$(tm display-message -p -t s:sub '#{pane_id}') "$AS" done
t "turn ended with 2 running: not done (no @done, no bordô)" "$(opt s:sub @done)|$(opt s:sub window-status-style)" "|fg=#8a8a8a"
hk sub-
t "stop 1: count 1, still not done" "$(opt s:sub @subagents)|$(opt s:sub @done)" "1|"
hk sub-
t "stop 2 after the turn ended: ✓ lit" "$(opt s:sub @done)|$(opt s:sub window-status-format)|$(opt s:sub @subagents)" "1| ✓ #W |"
hk sub-
t "never below 0" "$(opt s:sub @subagents)" ""
echo "--- list-windows"; tm list-windows -t s -F '#{window_name} subagents=[#{@subagents}] done=[#{@done}] fmt=[#{window-status-format}]' | sed 's/^/  /'
AGENT_STATE_ICON='⚙' hk sub+ ; tm set-option -w -t s:sub @subagents 1; AGENT_STATE_ICON='⚙' hk sub+
t "fallback glyph via AGENT_STATE_ICON" "$(opt s:sub window-status-format)" ' ⚙2 #W '

exec 9>&-
printf '%s passed, %s failed\n' "$pass" "$failn"; [ "$failn" = 0 ]
