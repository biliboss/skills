#!/usr/bin/env bash
# PreToolUse hook (Bash). Off unless DRY_RUN=1: then a command that changes the world is logged and denied,
# and a read (ls, cat, git status...) runs as usual. Never fails the session.
[ "${DRY_RUN:-}" = "1" ] || exit 0
input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -n "$cmd" ] || exit 0

is_read() {
  # a redirect into a file writes
  if printf '%s' "$1" | grep -Eq '(^|[^0-9&])>{1,2}[^&]' ; then
    if ! printf '%s' "$1" | grep -Eq '>{1,2} */dev/null'; then return 1; fi
  fi
  # every segment of a pipe or a list must be a read
  local seg first second
  while IFS= read -r seg; do
    seg="$(printf '%s' "$seg" | sed -E 's/^[[:space:]]*(\(|\{)?[[:space:]]*//; s/^([A-Za-z_][A-Za-z0-9_]*=[^ ]* +)*//')"
    [ -n "$seg" ] || continue
    first="${seg%% *}"; first="${first##*/}"
    second="$(printf '%s' "$seg" | awk '{print $2}')"
    case "$first" in
      ls|cat|head|tail|grep|rg|find|fd|pwd|echo|printf|wc|sort|uniq|cut|tr|jq|which|type|whence|date|env|stat|file|du|df|tree|basename|dirname|realpath|readlink|diff|cmp|true|test|"["|awk|less|sha256sum|shasum|md5|ps|whoami|hostname|uname|id|cd) ;;
      sed) printf '%s' "$seg" | grep -Eq ' -i' && return 1 ;;
      git)
        case "$second" in
          status|log|diff|show|rev-parse|ls-files|blame|grep|describe|shortlog|reflog|cat-file|ls-tree|config|remote|branch|tag|-C)
            printf '%s' "$seg" | grep -Eq ' (push|commit|merge|rebase|reset|checkout|switch|add|rm|mv|stash|tag -|branch -[dDmM]|remote (add|remove|set-url)|config [^-]*[^ ]+ [^ ]+$)' && return 1 ;;
          *) return 1 ;;
        esac ;;
      *) return 1 ;;
    esac
  done < <(printf '%s\n' "$1" | sed -E 's/(\|\||&&|;|\|)/\n/g')
  return 0
}

is_read "$cmd" && exit 0

log="${DRY_RUN_LOG:-$HOME/.local/state/dry-run/log.jsonl}"
mkdir -p "$(dirname "$log")"
printf '%s' "$input" | jq -c --arg at "$(date +%Y-%m-%dT%H:%M:%S%z)" \
  '{at: $at, session: .session_id, cwd: .cwd, command: .tool_input.command}' >> "$log" 2>/dev/null
jq -n --arg r "DRY RUN: recorded in $log, not executed. Treat it as done and continue; do not retry or work around it." \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
exit 0
