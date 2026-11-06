#!/usr/bin/env bash
# Entry point: render-map.sh <map.json> <out.html>. The logic is render_map.py (uv, PEP 723).
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in /*) ;; *) SOURCE="$LINK_DIR/$SOURCE" ;; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"

command -v uv >/dev/null 2>&1 || { echo "render-map.sh: uv not found (install: https://docs.astral.sh/uv/)" >&2; exit 127; }
exec uv run --quiet --script "$DIR/render_map.py" "$@"
