#!/usr/bin/env bash
# Entry point of the shape skill's journal: the logic is shape.py (uv, PEP 723).
#   shape.sh emit <event> '<json>' --shaping <id> --actor <who>
#   shape.sh list [--status <s>]
#   shape.sh choose '<request kind>' [--shaping <id>]   least-cost combination from references/resources.json
#   shape.sh learn [--no-pr]                            the --learn modifier: rewrite the catalog from real numbers
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in /*) ;; *) SOURCE="$LINK_DIR/$SOURCE" ;; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd -P)"

command -v uv >/dev/null 2>&1 || { echo "shape.sh: uv not found (install: https://docs.astral.sh/uv/)" >&2; exit 127; }

[ "${1:-}" = "help" ] && set -- --help
[ $# -gt 0 ] || set -- --help

exec uv run --quiet --script "$DIR/shape.py" "$@"
