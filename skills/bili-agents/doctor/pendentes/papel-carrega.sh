#!/usr/bin/env bash
# category: Roles
# what: a role is loaded when the agent starts: ag-spawn passes AG_ROLE and the session-start hook injects the role card
# fix: make ag-spawn put AG_ROLE=<role> in the command, and add scripts/session-start.sh to the skill: with AG_ROLE set it prints {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"<voice and the roles-<role> card>"}}; wire it in the --settings that ag-spawn generates
R="$(dirname "$AG_SKILL")"
out="$("$BIN/ag-spawn" -n --papel hacker demo-agent "$AG_HOME" 2>&1)" || { echo "ag-spawn -n failed: $out"; exit 1; }
case "$out" in *"AG_ROLE=hacker"*) ;; *) echo "ag-spawn does not pass AG_ROLE=hacker"; exit 1 ;; esac
H="$R/bili-agents/scripts/session-start.sh"
[ -x "$H" ] || { echo "scripts/session-start.sh is missing or not executable"; exit 1; }
j="$(AG_ROLE=hacker AG_SKILLS_DIR="$R" "$H" 2>&1)" || { echo "session-start.sh failed"; exit 1; }
printf '%s' "$j" | jq -e '.hookSpecificOutput.hookEventName=="SessionStart"' >/dev/null 2>&1 || { echo "session-start.sh did not print SessionStart JSON"; exit 1; }
printf '%s' "$j" | jq -r '.hookSpecificOutput.additionalContext' | grep -q '## Mission' || { echo "the roles-hacker card is not in additionalContext"; exit 1; }
none="$(env -u AG_ROLE AG_SKILLS_DIR="$R" "$H" 2>&1)"
printf '%s' "$none" | jq -r '.hookSpecificOutput.additionalContext // ""' | grep -q '## Mission' && { echo "without AG_ROLE no role card should be injected"; exit 1; }
echo "ag-spawn passes AG_ROLE and the session-start hook injects the role card (and none without a role)"
