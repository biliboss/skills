#!/usr/bin/env bash
# Kept so `second.sh [port] [--from 5057] --owner <name>` still works; the logic lives in console.sh.
exec "$(cd "$(dirname "$0")" && pwd)/console.sh" start "$@"
