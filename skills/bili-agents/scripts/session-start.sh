#!/usr/bin/env bash
# session-start.sh: the SessionStart hook of every agent opened by ag-spawn. It loads the agent's role.
#
# With AG_ROLE=<role> it prints the SessionStart JSON that adds the roles-<role> card (the body of that skill's SKILL.md,
# without frontmatter) to the session context, so the role is there from the first message and survives /clear. Without
# AG_ROLE it prints nothing: an agent with no role just works. The voice does not come from here: it is the plugin's output
# style, chosen by ag-spawn in the generated --settings.
#
# The card is found next to this skill: <skills>/roles-<role>/SKILL.md (AG_SKILLS_DIR overrides <skills>).
# Never blocks the session: always exits 0.
. "$(dirname "$0")/ag-lib.sh"

role="${AG_ROLE:-}"
[ -n "$role" ] || exit 0
printf '%s' "$role" | grep -qE '^[a-z][a-z0-9-]{0,31}$' || { echo "session-start: invalid AG_ROLE '$role'" >&2; exit 0; }

skills="${AG_SKILLS_DIR:-$(dirname "$AG_SKILL")}"
card="$skills/roles-$role/SKILL.md"
[ -f "$card" ] || { echo "session-start: no role card at $card" >&2; exit 0; }

# the card body: everything after the closing --- of the frontmatter
body="$(awk 'BEGIN{n=0} /^---$/ && n<2 {n++; next} n>=2' "$card")"
jq -n --arg role "$role" --arg body "$body" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: ("Your role in this session is \($role). It tells you how to work; the project folder tells you what you can do.\n\n" + $body)}}'
exit 0
