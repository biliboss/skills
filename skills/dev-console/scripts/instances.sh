#!/usr/bin/env bash
# Kept so `instances.sh list|start|stop` still works; the logic lives in console.sh.
exec "$(cd "$(dirname "$0")" && pwd)/console.sh" "$@"
