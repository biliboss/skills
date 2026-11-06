#!/usr/bin/env bash
# A second, independent dev-console: the same project and the same domains, its own port, and no live reload, so a
# save by the other agent never reloads this window. One instance per agent.
#   second.sh [port] [--from <port>]   default 5058, copying the domains of the instance on 5057
# The domains are the `--project` flags of the running instance (read from its command line) plus the registry
# (domains.txt, which every instance reads anyway); with no instance running, only this skill's own domain.
# Runs in the foreground: put it in a terminal tab of its own.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
port=5058 from=5057
while [ $# -gt 0 ]; do
  case "$1" in
    --from) from="$2"; shift 2 ;;
    *) port="$1"; shift ;;
  esac
done
if lsof -ti "tcp:$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "port $port is taken; pass another: second.sh 5059" >&2; exit 1; fi

projects=()
pid=$(lsof -ti "tcp:$from" -sTCP:LISTEN 2>/dev/null | head -1 || true)
if [ -n "$pid" ]; then
  # the listener may be a multiprocessing child: walk up to the process that carries the --project flags
  for _ in 1 2 3; do
    cmd=$(ps -o command= -p "$pid" 2>/dev/null || true)
    case "$cmd" in *--project*) break ;; esac
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    [ -n "$pid" ] || break
  done
  set -- $cmd
  while [ $# -gt 0 ]; do
    [ "$1" = "--project" ] && [ $# -gt 1 ] && projects+=(--project "$2")
    shift
  done
fi
[ ${#projects[@]} -gt 0 ] || projects=(--project "$here/dev_console_project.py")

echo "dev-console (no live reload): http://127.0.0.1:$port/  (domains of :$from)"
exec uv run --script "$here/dev-console.py" "${projects[@]}" --port "$port" --no-live
