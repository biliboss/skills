#!/usr/bin/env bash
# category: Voice
# what: one voice for every agent, shipped by the plugin; no instance carries its own output style
# fix: put the single voice in the plugin (output-styles/bili.md or skills/bili-agents/voice.md, depending on the voice test), have ag-spawn apply it, and delete the per-instance .claude/output-styles and outputStyle settings
REPO="$(dirname "$(dirname "$AG_SKILL")")"
if [ -f "$REPO/output-styles/bili.md" ] || [ -f "$REPO/skills/bili-agents/voice.md" ]; then :; else
  echo "the plugin has no voice file (output-styles/bili.md or skills/bili-agents/voice.md)"; exit 1
fi
own=""
for d in "$AG_HOME"/*/; do
  n="$(basename "$d")"
  [ -f "$d/LEIA-ME.md" ] && continue          # retired instance kept as a backup
  [ -f "$d/AGENTS.md" ] || continue
  if find "$d/.claude/output-styles" -maxdepth 1 -name '*.md' 2>/dev/null | grep -q .; then own="$own $n"; continue; fi
  for s in "$d/.claude/settings.json" "$d/.claude/settings.local.json"; do
    [ -f "$s" ] && jq -e 'has("outputStyle")' "$s" >/dev/null 2>&1 && own="$own $n"
  done
done
[ -z "$own" ] || { echo "instances with their own output style:$own"; exit 1; }
echo "one voice, shipped by the plugin; no instance has its own"
