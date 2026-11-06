#!/usr/bin/env bash
# test-sort.sh: thread.sh sort on a PRIVATE tmux server (-L). Bands, MRU, the owner's tab pinned, numbering 1..N, debounce.
set -uo pipefail
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
unset TMUX TMUX_PANE
export TMUX_SOCKET="thread-sort-$$"
T="$HERE/thread.sh"
tm() { tmux -L "$TMUX_SOCKET" "$@"; }
trap 'tm kill-server 2>/dev/null' EXIT
pass=0; fail=0
t() { if [ "$2" = "$3" ]; then pass=$((pass+1)); echo "ok   $1"; else fail=$((fail+1)); echo "FAIL $1: got [$2] want [$3]"; fi; }
order() { tm list-windows -t =s -F '#{window_name}' | tr '\n' ' '; }
idx() { tm list-windows -t =s -F '#{window_index}' | tr '\n' ' '; }
act() { tm list-windows -t =s -F '#{window_active}#{window_name}' | sed -n 's/^1//p'; }
opt() { tm set-option -w -t "s:$1" "$2" "$3"; }

tm new-session -d -s s -n bili -x 100 -y 30 'sleep 600'
tm new-window -d -t s -n zsh 'sleep 600'
for n in a b c d e; do tm new-window -d -t s -n "$n" 'sleep 600'; opt "$n" @thread "$n"; done
tm select-window -t s:bili
t "start" "$(order)" "bili zsh a b c d e "

# idle, all touched at different times: MRU (highest @touched first), non-threads last
opt a @touched 100; opt b @touched 500; opt c @touched 300; opt d @touched 200; opt e @touched 400
"$T" sort s:bili --now
t "MRU inside the idle band, zsh last" "$(order)" "bili b e c d a zsh "
t "numbers 1..N" "$(idx)" "1 2 3 4 5 6 7 "

# bands: ◆/✓ first, then working, then idle; each by MRU
opt d @done 1; opt a @ask 1; opt c @agent working; opt e @subagents 2
"$T" sort s:bili --now
t "bands: needs owner (a ◆ newer? no: d 200 > a 100), working (e 400, c 300), idle (b)" "$(order)" "bili d a e c b zsh "

# the owner's tab never moves and keeps the focus
tm select-window -t s:c                       # c is tab 5
opt b @done 1; opt b @touched 900             # b now needs the owner and is the newest
"$T" sort s:bili --now
t "owner on c: c keeps its index (5)" "$(tm display-message -p -t s:c '#{window_index}')" 5
t "focus stayed on c" "$(act)" c
t "the others arranged around it" "$(order)" "bili b d a c e zsh "
t "numbers 1..N after moves" "$(idx)" "1 2 3 4 5 6 7 "

# stamping: sort <tab> sets @touched now (newer than everything set by hand)
tm select-window -t s:bili
opt b @done ""; tm set-option -w -u -t s:b @done
"$T" sort s:a --now
t "sort <tab> stamps @touched" "$([ "$(tm show-options -wqv -t s:a @touched)" -gt 900 ] && echo yes)" yes
t "a (◆, just touched) leads; d ✓; e,c working; b idle" "$(order)" "bili a d e c b zsh "

# a non-thread target is not stamped, the Bili stays first
"$T" sort s:zsh --now
t "zsh not stamped" "$(tm show-options -wqv -t s:zsh @touched)" ""
t "Bili first, zsh last" "$(order)" "bili a d e c b zsh "

# debounce: a burst of requests = one sort, ~2 s after the last
tm set-option -w -u -t s:a @ask; tm set-option -w -u -t s:d @done
THREAD_SORT_DEBOUNCE=1 "$T" sort s:b
t "debounced: nothing moved yet" "$(order)" "bili a d e c b zsh "
THREAD_SORT_DEBOUNCE=1 "$T" sort s:b
sleep 1.6
t "after the quiet window: one sort (b newest idle... e,c working first)" "$(order)" "bili e c b a d zsh "

# a gap in the numbers (a closed tab) is closed by the next sort
tm kill-window -t s:d
"$T" sort --now 2>/dev/null || "$T" sort s:bili --now
t "gap closed" "$(idx)" "1 2 3 4 5 6 "

printf '%s passed, %s failed\n' "$pass" "$fail"; [ "$fail" = 0 ]
