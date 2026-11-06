#!/usr/bin/env bash
# Kept so the documented `second.sh [port] [--from 5057] --owner <name>` still works; the logic lives in instances.sh.
exec "$(cd "$(dirname "$0")" && pwd)/instances.sh" start "$@"
