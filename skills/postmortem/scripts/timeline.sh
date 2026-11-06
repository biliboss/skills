#!/bin/sh
# A porta da skill: a linha do tempo dos eventos do NATS (só leitura). Os argumentos vão direto ao timeline.py.
exec uv run --script "$(dirname "$0")/timeline.py" "$@"
