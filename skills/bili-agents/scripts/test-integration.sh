#!/usr/bin/env bash
set -eu
S="$(cd "$(dirname "$(dirname "$0")")" && pwd -P)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export AG_HOME="$T/home" AG_SKILL="$S" AG_SKILLS_DIR="$(dirname "$S")"
mkdir -p "$AG_HOME" "$T/project"
for role in hacker hipster hustler qa; do
  card="$AG_SKILLS_DIR/roles-$role/SKILL.md"
  [ -f "$card" ] || { echo "missing role card: $role"; exit 1; }
  AG_ROLE="$role" "$S/scripts/session-start.sh" | jq -e '.hookSpecificOutput.additionalContext | contains("## Mission")' >/dev/null
done
[ -z "$(env -u AG_ROLE "$S/scripts/session-start.sh")" ]
"$S/scripts/ag-new" -n sample --role hacker --project "$T/project" > "$T/dry"
[ ! -e "$AG_HOME/sample" ]
"$S/scripts/ag-new" sample --role hacker --project "$T/project" > "$T/create"
[ -f "$AG_HOME/sample/MEMORY.md" ]
grep -q '@MEMORY.md' "$AG_HOME/sample/AGENTS.md"
[ "$(cat "$AG_HOME/sample/.role")" = hacker ]
if "$S/scripts/ag-new" sample --role hacker --project "$T/project" >/dev/null 2>&1; then echo 'overwrote an existing instance'; exit 1; fi
"$S/scripts/ag-spawn" -n sample | grep -q AG_ROLE=hacker
"$S/scripts/setup" --here >/dev/null
"$S/scripts/setup" --here | grep -q 'nothing to do'
[ -L "$AG_HOME/bin/ag-new" ]
[ ! -L "$AG_HOME/bin/ag-lib.sh" ]
git -C "$T/project" init -q
git -C "$T/project" -c user.name=Fixture -c user.email=fixture@example.invalid commit --allow-empty -qm fixture
"$S/scripts/ag-new" isolated --role qa --project "$T/project" --worktree "$T/project" >/dev/null
git -C "$AG_HOME/isolated" rev-parse --is-inside-work-tree | grep -q true
git -C "$T/project" worktree remove "$AG_HOME/isolated" --force
printf 'roles, SessionStart JSON, instance ownership, role inference, setup idempotency and isolated worktree verified\n'
