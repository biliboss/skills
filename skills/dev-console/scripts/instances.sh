#!/usr/bin/env bash
# Manage the running dev-console instances: who owns each, where it runs, what it shows.
#   instances.sh list
#   instances.sh start [port] [--from 5057] --owner <name>   foreground, no live reload, domains of :--from
#   instances.sh stop <port> [--force]                      5057 (the main one) needs --force
# An instance has no name of its own and renaming a terminal tab is awkward, so `start` records the owner in
# ~/.local/state/dev-console/instances/<port>.json; without that file, `list` says where the process runs instead.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
state="${DEV_CONSOLE_STATE:-$HOME/.local/state/dev-console}/instances"
# `tmux` is an alias to `new-session -A` in the owner's shell, so call the binary by path
tmux_bin=/opt/homebrew/bin/tmux
[ -x "$tmux_bin" ] || tmux_bin=$(command -v tmux 2>/dev/null || true)

die() { echo "instances.sh: $*" >&2; exit 1; }
alive() { kill -0 "$1" 2>/dev/null; }
ppid_of() { ps -o ppid= -p "$1" 2>/dev/null | tr -d ' ' || true; }
cmd_of() { ps -o command= -p "$1" 2>/dev/null || true; }
owner_file() { echo "$state/$1.json"; }
forget() { [ -e "$1" ] && command rm -f -- "$1"; return 0; }

# The listener is often a multiprocessing child of `python dev-console.py`, itself a child of `uv run --script`.
# Walk up while the ancestors still run dev-console.py; the topmost one is what to kill and what carries the
# tty, the start time and the herdr env. Prints "<root pid> <python pid>" (python = lowest, has the flags).
instance_pids() { # <port>
  local pid root="" py="" cmd
  pid=$(lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)
  for _ in 1 2 3 4 5 6; do
    [ -n "$pid" ] && [ "$pid" != 0 ] && [ "$pid" != 1 ] || break
    cmd=$(cmd_of "$pid")
    case "$cmd" in
      *dev-console.py*) root=$pid; [ -n "$py" ] || py=$pid ;;
      *) [ -z "$root" ] || break ;;
    esac
    pid=$(ppid_of "$pid")
  done
  [ -n "$root" ] && echo "$root $py"
}

listening_ports() {
  lsof -nP -iTCP -sTCP:LISTEN -Fn 2>/dev/null | sed -n 's/^n.*:\([0-9][0-9]*\)$/\1/p' | sort -un
}

# the `--project` paths in a command line, one per line
project_flags() { # <command line>
  set -- $1
  while [ $# -gt 0 ]; do
    [ "$1" = "--project" ] && [ $# -gt 1 ] && echo "$2"
    shift
  done
}

# a domain's short name: the skill folder for <skill>/scripts/dev_console_project.py, else the file's name
short_domain() {
  local p="$1" d
  d=$(dirname "$p")
  if [ "$(basename "$p")" = dev_console_project.py ]; then
    [ "$(basename "$d")" = scripts ] && d=$(dirname "$d")
    basename "$d"
  else
    basename "$p" .py
  fi
}

# where a process runs, for an instance without an owner file: herdr pane, tmux pane, else the tty.
# herdr panes have no tty to match, but the shell inside one exports HERDR_PANE_ID to everything it starts.
where_of() { # <root pid>
  local pid="$1" pane tty ws tab line wsid tabid label
  pane=$(ps -Eww -p "$pid" -o command= 2>/dev/null | grep -o 'HERDR_PANE_ID=[^ ]*' | head -1 | cut -d= -f2 || true)
  if [ -n "$pane" ] && command -v herdr >/dev/null; then
    line=$(herdr pane list 2>/dev/null | jq -r --arg p "$pane" \
      '.result.panes[] | select(.pane_id==$p) | [.workspace_id, .tab_id, (.label // .pane_id)] | @tsv' || true)
    if [ -n "$line" ]; then
      IFS=$'\t' read -r wsid tabid label <<<"$line"
      ws=$(herdr workspace list 2>/dev/null | jq -r --arg i "$wsid" '.result.workspaces[] | select(.workspace_id==$i) | .label' || true)
      tab=$(herdr tab list 2>/dev/null | jq -r --arg i "$tabid" '.result.tabs[] | select(.tab_id==$i) | .label' || true)
      echo "herdr ${ws:-$wsid} / ${tab:-$tabid} / $label"
      return
    fi
  fi
  tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ' || true)
  if [ -n "$tty" ] && [ "$tty" != "??" ] && [ -n "$tmux_bin" ]; then
    line=$("$tmux_bin" list-panes -a -F '#{pane_tty} #{session_name}:#{window_index}.#{pane_index}' 2>/dev/null \
      | awk -v t="/dev/$tty" '$1==t {print $2; exit}' || true)
    if [ -n "$line" ]; then echo "tmux $line"; return; fi
  fi
  echo "tty ${tty:-none}"
}

cmd_list() {
  command -v jq >/dev/null || die "jq is required"
  local f p pids root py cmd found=0 owner script code live domains d
  # drop owner files whose process is gone, so a reused port does not inherit an old owner
  for f in "$state"/*.json; do
    [ -e "$f" ] || continue
    p=$(jq -r '.pid // empty' "$f" 2>/dev/null || true)
    if [ -z "$p" ] || ! alive "$p"; then forget "$f"; fi
  done
  for p in $(listening_ports); do
    pids=$(instance_pids "$p") || continue
    read -r root py <<<"$pids"
    cmd=$(cmd_of "$py")
    found=1
    owner="" domains=""
    f=$(owner_file "$p")
    # trust the file only when it was written for this very process
    if [ -f "$f" ] && [ "$(jq -r '.pid // empty' "$f")" = "$root" ]; then
      owner=$(jq -r '.owner // empty' "$f")
    fi
    script=$(echo "$cmd" | grep -o '[^ ]*dev-console\.py' | head -1)
    code=$(git -C "$(dirname "$script")" rev-parse --show-toplevel 2>/dev/null || dirname "$script")
    case "$cmd" in *--no-live*) live=off ;; *) live=on ;; esac
    while read -r d; do
      [ -n "$d" ] && domains="${domains:+$domains, }$(short_domain "$d")"
    done < <(project_flags "$cmd")
    printf ':%s\n' "$p"
    if [ -n "$owner" ]; then
      printf '  owner:    %s\n' "$owner"
    else
      printf '  owner:    (none recorded) runs in %s\n' "$(where_of "$root")"
    fi
    printf '  code:     %s\n' "$code"
    printf '  domains:  %s\n' "${domains:-(registry only)}"
    printf '  live:     %s\n' "$live"
    printf '  started:  %s (pid %s)\n' "$(ps -o lstart= -p "$root" | xargs)" "$root"
  done
  [ "$found" = 1 ] || echo "no dev-console instance is running"
}

cmd_start() {
  local port=5058 from=5057 owner="" pids py p projects=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --from) from="$2"; shift 2 ;;
      --owner) owner="$2"; shift 2 ;;
      *) port="$1"; shift ;;
    esac
  done
  [ -n "$owner" ] || die "--owner <name> is required (it is how this instance is told apart in \`list\`)"
  if lsof -ti "tcp:$port" -sTCP:LISTEN >/dev/null 2>&1; then die "port $port is taken; pass another: instances.sh start 5059 --owner $owner"; fi

  if pids=$(instance_pids "$from"); then
    read -r _ py <<<"$pids"
    while read -r p; do [ -n "$p" ] && projects+=(--project "$p"); done < <(project_flags "$(cmd_of "$py")")
  fi
  [ ${#projects[@]} -gt 0 ] || projects=(--project "$here/dev_console_project.py")

  # exec keeps this pid, so the file's pid is the uv process that `list` and `stop` find by port
  mkdir -p "$state"
  jq -n --argjson port "$port" --arg owner "$owner" --argjson pid "$$" \
    --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --argjson from "$from" \
    '{port: $port, owner: $owner, pid: $pid, started_at: $at, from: $from}' >"$(owner_file "$port")"
  echo "dev-console (no live reload, owner $owner): http://127.0.0.1:$port/  (domains of :$from)"
  exec uv run --script "$here/dev-console.py" "${projects[@]}" --port "$port" --no-live
}

# the pid and all its descendants, deepest first, so no child is orphaned by killing its parent
tree() {
  local c
  for c in $(pgrep -P "$1" 2>/dev/null || true); do tree "$c"; done
  echo "$1"
}

cmd_stop() {
  local port="" force=0 pids root pid all
  while [ $# -gt 0 ]; do
    case "$1" in
      --force) force=1; shift ;;
      *) port="$1"; shift ;;
    esac
  done
  [ -n "$port" ] || die "usage: instances.sh stop <port> [--force]"
  if [ "$port" = 5057 ] && [ "$force" != 1 ]; then die "5057 is the main instance; pass --force to stop it"; fi
  pids=$(instance_pids "$port") || { forget "$(owner_file "$port")"; die "no dev-console instance on port $port"; }
  read -r root _ <<<"$pids"
  all=$(tree "$root")
  for pid in $all; do kill "$pid" 2>/dev/null || true; done
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    alive "$root" || break
    sleep 0.3
  done
  for pid in $all; do if alive "$pid"; then kill -9 "$pid" 2>/dev/null || true; fi; done
  forget "$(owner_file "$port")"
  echo "stopped the instance on :$port"
}

case "${1:-}" in
  list) shift; cmd_list "$@" ;;
  start) shift; cmd_start "$@" ;;
  stop) shift; cmd_stop "$@" ;;
  *) echo "usage: instances.sh list | start [port] [--from 5057] --owner <name> | stop <port> [--force]" >&2; exit 2 ;;
esac
