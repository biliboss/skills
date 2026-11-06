#!/bin/bash
# claude-usage.sh: the weekly limit of the owner's two Claude accounts, read from Anthropic's OAuth usage endpoint
# with Claude Code's own login of each account (macOS keychain entry of its CLAUDE_CONFIG_DIR). Never refreshes or
# prints a token. Writes ~/.local/state/dev-console/claude-usage.json and prints it:
#   {"at": ISO, "accounts": [{"name":"mukutu","week":100,"h5":12,"resets":ISO} | {"name":..,"error":".."}]}
# Accounts: CLAUDE_USAGE_ACCOUNTS="mukutu=~/.claude-mukutu pessoal=~/.claude-pessoal" (default).
set -u
OUT=${CLAUDE_USAGE_OUT:-$HOME/.local/state/dev-console/claude-usage.json}
mkdir -p "$(dirname "$OUT")"
one() {  # name config-dir
  local dir=${2/#\~/$HOME} svc tok u
  svc="Claude Code-credentials-$(printf '%s' "$dir" | shasum -a 256 | cut -c1-8)"
  tok=$(security find-generic-password -s "$svc" -w 2>/dev/null | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
  [ -n "$tok" ] || { jq -cn --arg n "$1" '{name:$n, error:"sem login"}'; return; }
  u=$(curl -s -m 10 https://api.anthropic.com/api/oauth/usage -H "Authorization: Bearer $tok" -H "anthropic-beta: oauth-2025-04-20")
  jq -cn --arg n "$1" --argjson u "${u:-null}" 'if ($u|type)=="object" and $u.seven_day
    then {name:$n, week:($u.seven_day.utilization|floor), h5:(($u.five_hour.utilization // 0)|floor), resets:$u.seven_day.resets_at}
    else {name:$n, error:(($u.error.message // "falhou")|.[0:60])} end' 2>/dev/null || jq -cn --arg n "$1" '{name:$n, error:"falhou"}'
}
rows=()
for pair in ${CLAUDE_USAGE_ACCOUNTS:-mukutu=~/.claude-mukutu pessoal=~/.claude-pessoal}; do rows+=("$(one "${pair%%=*}" "${pair#*=}")"); done
printf '%s\n' "${rows[@]}" | jq -cs '{at:(now|todate), accounts:.}' > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
cat "$OUT"
