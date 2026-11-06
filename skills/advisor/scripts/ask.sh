#!/usr/bin/env bash
# The advisor protocol's writes, so nobody hand-builds the jsonl line (nested jq escapes are where it breaks).
#   ask.sh ask   <thread> --task .. --goal .. --done .. --tried .. --question .. [--resource <file>]... [--actor <name>]
#   ask.sh reply <thread> <reply_to> --verdict segue|corrige|para --advice .. [--risk ..]... [--actor <name>]
#   ask.sh note  <thread> "<fact>" [--actor <name>]
#   ask.sh thread <thread>                 the thread's lines, one per row
# context.jsonl is append-only: one short line per event, so two writers appending at once never interleave. What does
# not fit in a line goes to resources/<thread>/ and the line carries only the path.
# Env: ADVISOR_DIR (default ~/.local/share/advisor; tests point it at a temp dir), ADVISOR_ACTOR (default "agente"),
#      ADVISOR_TO (the session SendMessage addresses, default "advisor").
set -euo pipefail

dir="${ADVISOR_DIR:-$HOME/.local/share/advisor}"
ctx="$dir/context.jsonl"
actor="${ADVISOR_ACTOR:-agente}"
to="${ADVISOR_TO:-advisor}"
MAX_LINE=3500  # under PIPE_BUF (4096 on macOS): one `>>` of a line this size is a single atomic write

die() { echo "ask.sh: $*" >&2; exit 1; }
command -v jq >/dev/null || die "jq is required (brew install jq)"

thread_ok() { [[ "$1" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || die "thread must be a short slug (letters, digits, dashes): $1"; }

# A resource is read by another session and stays on disk: refuse what looks like a secret.
secret_name() {
  case "$(basename "$1" | tr '[:upper:]' '[:lower:]')" in
    .env|.env.*|*.env|*.pem|*.key|*.p12|*.pfx|.sesskey|id_rsa*|id_ed25519*|*token*|*secret*|*credential*|.netrc) return 0 ;;
  esac
  return 1
}

# append <jq program> [jq args...]: build the line, check its size, write it with one `>>`
append() {
  local line
  line=$(jq -nc --arg id "$(uuidgen)" --arg at "$(date -u +%FT%TZ)" "$@")
  [ "${#line}" -le "$MAX_LINE" ] || die "the line is ${#line} bytes (max $MAX_LINE): put the long part in a --resource file"
  mkdir -p "$dir"
  printf '%s\n' "$line" >>"$ctx"
  printf '%s' "$line" | jq -r .id
}

cmd_ask() {
  local th="${1:-}"; shift || true
  [ -n "$th" ] || die "usage: ask.sh ask <thread> --task .. --goal .. --done .. --tried .. --question .. [--resource <file>]..."
  thread_ok "$th"
  local task="" goal="" done_="" tried="" question="" res=() a
  while [ $# -gt 0 ]; do
    [ $# -ge 2 ] || die "$1 needs a value"
    case "$1" in
      --task) task="$2" ;; --goal) goal="$2" ;; --done) done_="$2" ;; --tried) tried="$2" ;;
      --question) question="$2" ;; --resource) res+=("$2") ;; --actor) actor="$2" ;;
      *) die "unknown option: $1" ;;
    esac
    shift 2
  done
  for a in task goal done_ tried question; do [ -n "${!a}" ] || die "--${a%_} is required (the advisor does not see your transcript)"; done

  local paths=() f
  for f in ${res[@]+"${res[@]}"}; do
    [ -f "$f" ] || die "resource is not a file: $f"
    if secret_name "$f"; then die "refusing $f: it looks like a secret (.env, key, token, .sesskey)"; fi
    mkdir -p "$dir/resources/$th"
    cp -- "$f" "$dir/resources/$th/$(basename "$f")"
    paths+=("resources/$th/$(basename "$f")")
  done
  local resj
  resj=$(jq -nc '$ARGS.positional' --args ${paths[@]+"${paths[@]}"})
  local id
  id=$(append '{id:$id, at:$at, actor:$actor, event:"question.asked", thread:$th,
                value:{task:$task, goal:$goal, done:$done, tried:$tried, question:$q, resources:$res}}' \
    --arg actor "$actor" --arg th "$th" --arg task "$task" --arg goal "$goal" --arg done "$done_" \
    --arg tried "$tried" --arg q "$question" --argjson res "$resj")
  echo "$id"
  echo "now send it with SendMessage: to \"$to\", first line: pergunta $id na thread $th" >&2
}

cmd_reply() {
  local th="${1:-}" re="${2:-}"; shift 2 || true
  [ -n "$th" ] && [ -n "$re" ] || die "usage: ask.sh reply <thread> <reply_to> --verdict segue|corrige|para --advice .. [--risk ..]..."
  thread_ok "$th"
  local verdict="" advice="" risks=()
  while [ $# -gt 0 ]; do
    [ $# -ge 2 ] || die "$1 needs a value"
    case "$1" in
      --verdict) verdict="$2" ;; --advice) advice="$2" ;; --risk) risks+=("$2") ;; --actor) actor="$2" ;;
      *) die "unknown option: $1" ;;
    esac
    shift 2
  done
  [[ "$verdict" =~ ^(segue|corrige|para)$ ]] || die "--verdict must be segue, corrige or para"
  [ -n "$advice" ] || die "--advice is required"
  if [ -f "$ctx" ] && ! jq -e --arg re "$re" --arg th "$th" 'select(.id==$re and .thread==$th and .event=="question.asked")' "$ctx" >/dev/null 2>&1; then
    echo "ask.sh: warning: no question.asked $re on thread $th" >&2
  fi
  local riskj
  riskj=$(jq -nc '$ARGS.positional' --args ${risks[@]+"${risks[@]}"})
  local id
  id=$(append '{id:$id, at:$at, actor:$actor, event:"advice.given", thread:$th,
                value:{reply_to:$re, verdict:$v, advice:$adv, risks:$risks}}' \
    --arg actor "$actor" --arg th "$th" --arg re "$re" --arg v "$verdict" --arg adv "$advice" --argjson risks "$riskj")
  echo "$id"
  echo "now answer with SendMessage to the sender of the question, same text" >&2
}

cmd_note() {
  local th="${1:-}" fact="${2:-}"; shift 2 || true
  [ -n "$th" ] && [ -n "$fact" ] || die "usage: ask.sh note <thread> \"<fact>\""
  thread_ok "$th"
  while [ $# -gt 0 ]; do
    [ "$1" = --actor ] && [ $# -ge 2 ] || die "unknown option: $1"
    actor="$2"; shift 2
  done
  append '{id:$id, at:$at, actor:$actor, event:"context.added", thread:$th, value:{fact:$fact}}' \
    --arg actor "$actor" --arg th "$th" --arg fact "$fact"
}

cmd_thread() {
  local th="${1:-}"
  [ -n "$th" ] || die "usage: ask.sh thread <thread>"
  [ -f "$ctx" ] || die "no context yet: $ctx"
  jq -r --arg th "$th" 'select(.thread==$th) | "\(.at) \(.actor) \(.event) \(.id)\n    \(.value | tostring | .[0:600])"' "$ctx"
}

case "${1:-}" in
  ask) shift; cmd_ask "$@" ;;
  reply) shift; cmd_reply "$@" ;;
  note) shift; cmd_note "$@" ;;
  thread) shift; cmd_thread "$@" ;;
  *) echo "usage: ask.sh ask|reply|note|thread <thread> ... (see the header of this script)" >&2; exit 2 ;;
esac
