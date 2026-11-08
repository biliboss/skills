#!/usr/bin/env bash
# category: Code vs data
# what: the skill scripts hold no machine paths; code finds itself by dirname, data lives in AG_HOME
# fix: replace hardcoded /Users/... and ~/agents/skills/bili-agents paths in the skill scripts with AG_SKILL (the script directory) and AG_HOME (the data home)
R="$AG_SKILL"
[ -d "$R/scripts" ] || { echo "skill scripts directory is missing"; exit 1; }
hit="$(grep -rnE '/Users/|agents/skills/bili-agents|AG_HOME/skills' "$R/scripts" 2>/dev/null | grep -vE '^[^:]*:[0-9]+:[[:space:]]*#' | head -3)"
[ -z "$hit" ] || { echo "machine path in the skill: $(printf '%s' "$hit" | head -1 | cut -c1-140)"; exit 1; }
grep -q 'AG_SKILL' "$R/scripts/ag-lib.sh" || { echo "ag-lib.sh does not define AG_SKILL"; exit 1; }
echo "no machine paths in the skill scripts; AG_SKILL and AG_HOME split code from data"
