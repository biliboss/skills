#!/usr/bin/env bash
set -euo pipefail
exec uv run --quiet --script "$(dirname "$0")/self_learning.py" "$@"
