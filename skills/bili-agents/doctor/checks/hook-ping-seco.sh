#!/usr/bin/env bash
# category: Runtime
# what: the ping hook serves ALL bili-agents agents and answers WHO ASKED (dry mode: sends nothing)
# fix: make scripts/manager-send-back.sh print "[agent] finished: ...", "[agent] question: ..." and "[agent] needs you: ..." in dry mode, take the agent name from the hook's cwd (~/agents/<name>), and resolve the target with --quem (PING_ASKER, then the asker label, then .manager-pane)
H="$AG_SKILL/scripts/manager-send-back.sh"
[ -x "$H" ] || { echo "missing $H"; exit 1; }
a="$(echo '{"hook_event_name":"Stop","last_assistant_message":"done"}' | PING_DRY=1 PING_NOME=demo "$H")"
b="$(echo '{"hook_event_name":"PreToolUse","tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"may I?"}]}}' | PING_DRY=1 PING_NOME=demo "$H")"
c="$(echo '{"hook_event_name":"Notification","message":"permission"}' | PING_DRY=1 PING_NOME=demo "$H")"
case "$a" in "[demo] finished: done") ;; *) echo "Stop: '$a'"; exit 1 ;; esac
case "$b" in "[demo] question: may I?") ;; *) echo "AskUserQuestion: '$b'"; exit 1 ;; esac
case "$c" in "[demo] needs you: permission") ;; *) echo "Notification: '$c'"; exit 1 ;; esac

# the agent name comes from the folder (the hook's cwd) when there is no PING_NOME: any agent in ~/agents/<name>
d="$(echo '{"hook_event_name":"Stop","last_assistant_message":"ok","cwd":"'"$AG_HOME"'/demo-agent/repo"}' | PING_DRY=1 "$H")"
case "$d" in "[demo-agent] finished: ok") ;; *) echo "name from cwd: '$d'"; exit 1 ;; esac

# who to answer (--quem prints the target): 1) PING_ASKER; 2) the asker label of the agent's terminal (tested live in ag-selftest); 3) the manager in .manager-pane
q1="$(PING_ASKER=t99 "$H" --quem 2>&1)"
[ "$q1" = "t99" ] || { echo "--quem with PING_ASKER: '$q1'"; exit 1; }
tmp="$(mktemp)"; printf 't7\n' > "$tmp"
q2="$(env -u PING_ASKER -u HC_TERMINAL_ID MANAGER_PANE_FILE="$tmp" "$H" --quem 2>&1)"
rm -f "$tmp" 2>/dev/null
[ "$q2" = "t7" ] || { echo "--quem without a label should fall back to the manager (t7): '$q2'"; exit 1; }
echo "Stop, question and permission lines ok; name from cwd; target from the asker or the manager"
