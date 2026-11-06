#!/usr/bin/env bash
# Shared by decide.sh, rate.sh and decisions.sh (sourced, never run). decisions.jsonl is append-only like context.jsonl:
# one short line per fact, never rewritten; a wrong line is answered by a later one.
dir="${ADVISOR_DIR:-$HOME/.local/share/advisor}"
decisions="$dir/decisions.jsonl"
actor="${ADVISOR_ACTOR:-agente}"
MAX_LINE=3500  # under PIPE_BUF: one `>>` of a line this size is a single atomic write

die() { echo "$(basename "$0"): $*" >&2; exit 1; }
command -v jq >/dev/null || die "jq is required (brew install jq)"

thread_ok() { [[ "$1" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || die "thread must be a short slug (letters, digits, dashes): $1"; }
moment_ok() { [[ "$1" =~ ^(plano|travou|terminou|irreversivel|ambiguidade)$ ]] || die "--moment must be plano, travou, terminou, irreversivel or ambiguidade"; }
bool_ok() { [[ "$2" =~ ^(true|false)$ ]] || die "$1 must be true or false"; }

# append_decision <jq program> [jq args...]: build the line, check its size, write it with one `>>`, print its id
append_decision() {
  local line
  line=$(jq -nc --arg id "$(uuidgen)" --arg at "$(date -u +%FT%TZ)" --arg actor "$actor" "$@")
  [ "${#line}" -le "$MAX_LINE" ] || die "the line is ${#line} bytes (max $MAX_LINE): shorten the text"
  mkdir -p "$dir"
  printf '%s\n' "$line" >>"$decisions"
  printf '%s' "$line" | jq -r .id
}
