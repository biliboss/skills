#!/usr/bin/env bash
# Drive Hermes profiles from Claude Code or pi. Logic lives in hermes.py (PEP 723, stdlib only).
set -euo pipefail

src="${BASH_SOURCE[0]}"
while [ -L "$src" ]; do
  dir="$(cd -P "$(dirname "$src")" && pwd)"
  src="$(readlink "$src")"
  case "$src" in /*) ;; *) src="$dir/$src" ;; esac
done
here="$(cd -P "$(dirname "$src")" && pwd)"

if command -v uv >/dev/null 2>&1; then
  exec uv run --quiet --script "$here/hermes.py" "$@"
fi
exec python3 "$here/hermes.py" "$@"
