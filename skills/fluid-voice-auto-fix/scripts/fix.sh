#!/bin/sh
# fix.sh — mantém o dicionário e o vocabulário do FluidVoice. Ver ../SKILL.md.
#   add <gatilho...> -- <substituição> | boost <termo> [alias...] | list | backup | restore <arquivo> | scan [--top N]
set -eu
here=$(cd "$(dirname "$0")" && pwd)
command -v uv >/dev/null 2>&1 || { echo "erro: precisa do uv (brew install uv)" >&2; exit 127; }
exec uv run --quiet --script "$here/fluid.py" "$@"
