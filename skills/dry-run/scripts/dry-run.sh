#!/usr/bin/env bash
# dry-run: read what a DRY_RUN=1 session would have run.
set -euo pipefail
log="${DRY_RUN_LOG:-$HOME/.local/state/dry-run/log.jsonl}"
case "${1:-log}" in
  status) if [ "${DRY_RUN:-}" = "1" ]; then echo "on (this shell)"; else echo "off (this shell)"; fi; echo "log: $log" ;;
  log) n="${2:-20}"; if [ -f "$log" ]; then tail -n "$n" "$log" | jq -r '"\(.at)  \(.cwd)\n  $ \(.command)"'; else echo "empty"; fi ;;
  clear) : > "$log"; echo "cleared $log" ;;
  *) echo "usage: dry-run.sh status | log [n] | clear   (turn on: DRY_RUN=1 claude)" >&2; exit 2 ;;
esac
