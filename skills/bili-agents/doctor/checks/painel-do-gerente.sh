#!/usr/bin/env bash
# what: the manager's terminal (the agent that drives the others) is registered and still exists in the herdr Desktop (hc)
F="$AG_HOME/.manager-pane"
[ -s "$F" ] || { echo "missing $F (run manager-send-back.sh --set inside the manager's terminal, in the Desktop)"; exit 1; }
t="$(command cat "$F")"
case "$t" in t[0-9a-z]*) ;; *) echo "the registered one ($t) is not an hc address (tN); run manager-send-back.sh --set again inside the Desktop"; exit 1 ;; esac
hc get "$t" >/dev/null 2>&1 || { echo "terminal $t no longer exists"; exit 1; }
echo "manager at $t"
