#!/usr/bin/env bash
# project-state: read or set a repo's declared state (.project-state at the git root; none = draft).
set -euo pipefail
cmd="${1:-get}"
shift || true

root_of() {
  if ! git -C "${1:-.}" rev-parse --show-toplevel 2>/dev/null; then
    echo "not a git repo: ${1:-.}" >&2
    exit 2
  fi
}

case "$cmd" in
  get)
    r="$(root_of "${1:-.}")"
    s=""
    if [ -f "$r/.project-state" ]; then s="$(tr -d '[:space:]' < "$r/.project-state")"; fi
    echo "${s:-draft}"
    ;;
  set)
    s="${1:-}"
    case "$s" in draft|live) ;; *) echo "usage: state.sh set draft|live [dir]" >&2; exit 2 ;; esac
    r="$(root_of "${2:-.}")"
    echo "$s" > "$r/.project-state"
    echo "$r: $s"
    ;;
  *)
    echo "usage: state.sh get [dir] | set draft|live [dir]" >&2
    exit 2
    ;;
esac
