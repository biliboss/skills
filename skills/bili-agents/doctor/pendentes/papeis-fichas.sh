#!/usr/bin/env bash
# category: Roles
# what: every roles-* card has the required sections and is generic (no person, no date, no project name)
# fix: edit skills/roles-<role>/SKILL.md so it has the sections Mission, How you work, Deliverable, Never, Leans on, Default model, and remove any person name, dd/mm date or project name (project rules belong to the instance)
S="$(dirname "$AG_SKILL")"
n=0
for r in hacker hipster hustler qa; do
  f="$S/roles-$r/SKILL.md"
  [ -f "$f" ] || { echo "roles-$r/SKILL.md is missing (no cards to validate)"; exit 1; }
  for sec in 'Mission' 'How you work' 'Deliverable' 'Never' 'Leans on' 'Default model'; do
    grep -qE "^## $sec\$" "$f" || { echo "roles-$r has no '## $sec' section"; exit 1; }
  done
  bad="$(grep -n -i -E 'owner|person|[0-9]{2}/[0-9]{2}|sample-project|sample project|demo-project|sample-org|sample-team|sample-group' "$f" | head -1)"
  [ -z "$bad" ] || { echo "roles-$r is not generic: $(printf '%s' "$bad" | cut -c1-100)"; exit 1; }
  n=$((n+1))
done
echo "$n role cards: all sections present, no person, date or project names"
