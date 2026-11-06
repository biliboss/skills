#!/usr/bin/env bash
# console.sh: the agent's one door to the dev-console (instances, domains, reading, links).
#
#   console.sh list                                   every running instance: owner, code, domains, live, start
#   console.sh start [port] --owner <n> [--from 5057] [--no-tab] [--dry-run]
#   console.sh stop <port> [--force]                  5057 (the main one) needs --force
#   console.sh claim <port> --owner <n>               record who owns an instance this script did not start
#   console.sh domains [port]                         slug, origin (--project | registry), path
#   console.sh domains add <path> | remove <path|slug>   edit the registry (domains.txt)
#   console.sh state <slug> [--port N] [--task <id>]  the page's data as JSON (pipe it to jq)
#   console.sh url <slug> [--port N] [--task <id>] [--tab X] [--ev X] [--side X] [--w X] [--e X]
#   console.sh actions [<slug>] [--port N]            the names in PROJECT.ACTIONS, per domain
#
# Who owns which instance lives in ONE append-only journal, $DEV_CONSOLE_STATE/instances.jsonl
# (default ~/.local/state/dev-console/), one event per line: {"id","event","at","actor","value"} with
# instance.started {port, owner, pid, from}, instance.claimed {port, owner, pid}, instance.stopped {port}.
# Nothing rewrites it: `list` projects the current owner per port from it, so an owner is whoever the last
# started/claimed event names for the pid that still listens there (a stop, or another process, means none).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
self="$here/console.sh"
state="${DEV_CONSOLE_STATE:-$HOME/.local/state/dev-console}"
journal="$state/instances.jsonl"
# the server's own registry (it honours DEV_CONSOLE_REGISTRY too), deliberately not under DEV_CONSOLE_STATE
registry="${DEV_CONSOLE_REGISTRY:-$HOME/.local/state/dev-console/domains.txt}"
# `tmux` is an alias to `new-session -A` in the owner's shell, so call the binary by path
tmux_bin=/opt/homebrew/bin/tmux
[ -x "$tmux_bin" ] || tmux_bin=$(command -v tmux 2>/dev/null || true)

die() { echo "console.sh: $*" >&2; exit 1; }
need_jq() { command -v jq >/dev/null || die "jq is required"; }
alive() { kill -0 "$1" 2>/dev/null; }
ppid_of() { ps -o ppid= -p "$1" 2>/dev/null | tr -d ' ' || true; }
cmd_of() { ps -o command= -p "$1" 2>/dev/null || true; }
is_port() { [[ "${1:-}" =~ ^[0-9]{2,5}$ ]]; }

# ---------------------------------------------------------------- the journal

# record <event> <value-json> [actor]: one line, written with jq and appended (never rewritten)
record() {
  mkdir -p "$state"
  jq -nc --arg id "$(uuidgen | tr 'A-Z' 'a-z')" --arg event "$1" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg actor "${3:-${USER:-unknown}}" --argjson value "$2" \
    '{id: $id, event: $event, at: $at, actor: $actor, value: $value}' >>"$journal"
}

# owner_of <port> <pid>: the projection. The latest event for this port that is a stop, or names this very pid;
# a stop (or none) means no owner. Lines that do not parse are skipped, so a torn write never hides the rest.
owner_of() {
  [ -f "$journal" ] || return 0
  jq -rnR --argjson port "$1" --argjson pid "$2" '
    [inputs | fromjson? | select(.value.port == $port)] | reverse
    | first(.[] | select(.event == "instance.stopped" or .value.pid == $pid))
    | select(.event != "instance.stopped") | .value.owner' "$journal" 2>/dev/null || true
}

# ---------------------------------------------------------------- finding instances

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

# A port is also taken when a running dev-console was started for it: while that server reloads, the socket is
# briefly unbound and lsof alone would let a duplicate start. No --port in the command line means the default 5057.
claimed() { # <port>
  local c
  while read -r c; do
    if echo "$c" | grep -qE -- "--port[ =]$1( |\$)"; then return 0; fi
    if [ "$1" = 5057 ] && ! echo "$c" | grep -q -- '--port'; then return 0; fi
  done < <(pgrep -fl 'dev-console\.py' 2>/dev/null | grep -v -- 'console\.sh' || true)
  return 1
}
taken() { lsof -ti "tcp:$1" -sTCP:LISTEN >/dev/null 2>&1 || claimed "$1"; }

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

# where a process runs, for an instance with no owner: herdr pane, tmux pane, else the tty.
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

# ---------------------------------------------------------------- domains

# slug_of <project file>: the rule dev-console.py uses (SLUG in the file, else the skill folder's name).
# Only for an instance too old to answer /api/domains; the API is the source of truth when it answers.
slug_of() {
  local p="$1" s
  s=$(sed -n 's/^SLUG *= *["'\'']\([^"'\'']*\)["'\''].*/\1/p' "$p" 2>/dev/null | head -1 || true)
  echo "${s:-$(basename "$(dirname "$(dirname "$p")")")}"
}

abs_path() { # <path>: absolute, symlinks resolved like the server does (Path.resolve)
  local d; d="$(cd "$(dirname "$1")" 2>/dev/null && pwd -P)" || return 1
  echo "$d/$(basename "$1")"
}

# registered: the registry's existing paths, absolute, one per line (what registered() does in the server)
registered() {
  local l p
  [ -f "$registry" ] || return 0
  while IFS= read -r l || [ -n "$l" ]; do
    l="${l%%$'\r'}"; l="$(echo "$l" | xargs 2>/dev/null || true)"
    case "$l" in ""|"#"*) continue ;; esac
    l="${l/#\~/$HOME}"
    p=$(abs_path "$l") || continue
    [ -e "$p" ] && echo "$p"
  done <"$registry"
}

# api <port> <path>: the body, or non-zero when the instance does not answer that route
api() {
  curl -sf --max-time 3 "http://127.0.0.1:$1$2" 2>/dev/null
}

# domain_rows <port>: "slug<TAB>origin<TAB>path" for every domain that instance shows
domain_rows() {
  local port="$1" body pids py cmd p seen=" "
  if body=$(api "$port" /api/domains) && [ -n "$body" ]; then
    echo "$body" | jq -r '.[] | [.slug, .origin, .path] | @tsv'
    return
  fi
  # an instance running older code: rebuild the list from its command line and the registry
  pids=$(instance_pids "$port") || die "no dev-console instance on port $port"
  read -r _ py <<<"$pids"
  cmd=$(cmd_of "$py")
  echo "(port $port has no /api/domains: derived from its command line and the registry)" >&2
  while read -r p; do
    [ -n "$p" ] || continue
    p=$(abs_path "$p") || continue
    seen+="$p "
    printf '%s\t--project\t%s\n' "$(slug_of "$p")" "$p"
  done < <(project_flags "$cmd")
  while read -r p; do
    case "$seen" in *" $p "*) continue ;; esac
    printf '%s\t%s\t%s\n' "$(slug_of "$p")" registry "$p"
  done < <(registered)
}

cmd_domains() {
  need_jq
  case "${1:-}" in
    add) shift; domains_add "$@" ;;
    remove) shift; domains_remove "$@" ;;
    *)
      local port="${1:-5057}"
      is_port "$port" || die "usage: console.sh domains [port] | add <path> | remove <path|slug>"
      domain_rows "$port" | awk -F'\t' 'BEGIN { printf "%-18s %-10s %s\n", "SLUG", "ORIGIN", "PATH" }
        { printf "%-18s %-10s %s\n", $1, $2, $3 }'
      ;;
  esac
}

domains_add() {
  local given="${1:-}" p
  [ -n "$given" ] || die "usage: console.sh domains add <path/to/dev_console_project.py>"
  given="${given/#\~/$HOME}"
  [ -f "$given" ] || die "$given does not exist (or is not a file)"
  p=$(abs_path "$given")
  if registered | grep -qxF -- "$p"; then echo "already in the registry: $p"; return 0; fi
  mkdir -p "$(dirname "$registry")"
  # the file may lack a final newline; do not glue two paths into one line
  if [ -s "$registry" ] && [ -n "$(tail -c1 "$registry")" ]; then echo >>"$registry"; fi
  echo "$p" >>"$registry"
  echo "added $p (slug $(slug_of "$p")); a running console picks it up by itself"
}

domains_remove() {
  local what="${1:-}" target="" p tmp l n=0
  [ -n "$what" ] || die "usage: console.sh domains remove <path|slug>"
  [ -f "$registry" ] || die "no registry at $registry"
  if [ -f "${what/#\~/$HOME}" ]; then
    target=$(abs_path "${what/#\~/$HOME}")
  else
    while read -r p; do
      if [ "$(slug_of "$p")" = "$what" ]; then target="$p"; n=$((n + 1)); fi
    done < <(registered)
    [ "$n" -le 1 ] || die "slug $what matches $n registry entries; pass the path"
  fi
  [ -n "$target" ] || die "$what is not in the registry (domains from --project flags are not removable here)"
  registered | grep -qxF -- "$target" || die "$target is not in the registry"
  tmp="$(mktemp "$registry.XXXXXX")"
  while IFS= read -r l || [ -n "$l" ]; do
    p="${l/#\~/$HOME}"
    if [ -n "$p" ] && [ "${l#\#}" = "$l" ] && [ -e "$p" ] && [ "$(abs_path "$p")" = "$target" ]; then continue; fi
    printf '%s\n' "$l"
  done <"$registry" >"$tmp"
  mv "$tmp" "$registry"
  echo "removed $target (a running console keeps showing it until it restarts)"
}

# ---------------------------------------------------------------- list

cmd_list() {
  need_jq
  local p pids root py cmd found=0 owner script code live domains rows
  for p in $(listening_ports); do
    pids=$(instance_pids "$p") || continue
    read -r root py <<<"$pids"
    cmd=$(cmd_of "$py")
    found=1
    owner=$(owner_of "$p" "$root")
    script=$(echo "$cmd" | grep -o '[^ ]*dev-console\.py' | head -1)
    code=$(git -C "$(dirname "$script")" rev-parse --show-toplevel 2>/dev/null || dirname "$script")
    case "$cmd" in *--no-live*) live=off ;; *) live=on ;; esac
    # every domain it shows (the --project ones and the registry's), flagged when it came from the registry
    rows=$(domain_rows "$p" 2>/dev/null || true)
    domains=$(echo "$rows" | awk -F'\t' 'NF { printf "%s%s%s", sep, $1, ($2 == "registry" ? " (registry)" : ""); sep = ", " }')
    printf ':%s\n' "$p"
    if [ -n "$owner" ]; then
      printf '  owner:    %s\n' "$owner"
    else
      printf '  owner:    (none recorded) runs in %s\n' "$(where_of "$root")"
    fi
    printf '  code:     %s\n' "$code"
    printf '  domains:  %s\n' "${domains:-(none)}"
    printf '  live:     %s\n' "$live"
    printf '  started:  %s (pid %s)\n' "$(ps -o lstart= -p "$root" | xargs)" "$root"
  done
  [ "$found" = 1 ] || echo "no dev-console instance is running"
}

# ---------------------------------------------------------------- start / stop / claim

# start_in_herdr <ws> <port> <owner> <from> <dry>: a tab `dev-console:<port>` in the workspace, running this same
# command with --no-tab (the skill's rule: the server is never an agent's background process)
start_in_herdr() {
  local ws="$1" port="$2" owner="$3" from="$4" dry="$5" label line pane i
  label="dev-console:$port"
  line="$self start $port --owner $owner --from $from --no-tab 2>&1 | tee -a $state/console-$port.log"
  if [ "$dry" = 1 ]; then
    echo "would: herdr tab create --workspace $ws --label $label --cwd ~ --no-focus"
    echo "would: herdr pane send-text <its root pane> '$line' then send-keys Enter"
    return 0
  fi
  pane=$(herdr tab create --workspace "$ws" --label "$label" --cwd "$HOME" --no-focus | jq -r '.result.root_pane.pane_id // empty')
  [ -n "$pane" ] || die "herdr tab create gave no pane"
  herdr pane send-text "$pane" "$line" >/dev/null
  herdr pane send-keys "$pane" Enter >/dev/null
  for i in $(seq 1 40); do
    if lsof -ti "tcp:$port" -sTCP:LISTEN >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
  echo "dev-console on :$port in herdr tab $label (pane $pane): http://127.0.0.1:$port/"
}

cmd_start() {
  need_jq
  local port="" from=5057 owner="" tab=1 dry=0 pids py p projects=() ws
  while [ $# -gt 0 ]; do
    case "$1" in
      --from) from="$2"; shift 2 ;;
      --owner) owner="$2"; shift 2 ;;
      --no-tab) tab=0; shift ;;
      --dry-run) dry=1; shift ;;
      *) is_port "$1" || die "unexpected argument: $1"; port="$1"; shift ;;
    esac
  done
  [ -n "$owner" ] || die "--owner <name> is required (it is how this instance is told apart in \`list\`)"
  if [ -z "$port" ]; then # the first free port from 5058
    port=5058
    while taken "$port"; do port=$((port + 1)); done
  elif taken "$port"; then
    die "port $port is taken; pass another, or omit it to take the next free one"
  fi

  if pids=$(instance_pids "$from"); then
    read -r _ py <<<"$pids"
    while read -r p; do [ -n "$p" ] && projects+=(--project "$p"); done < <(project_flags "$(cmd_of "$py")")
  fi
  [ ${#projects[@]} -gt 0 ] || projects=(--project "$here/dev_console_project.py")

  ws="${HERDR_WORKSPACE_ID:-}"
  if [ "$tab" = 1 ] && [ -n "$ws" ] && command -v herdr >/dev/null; then
    start_in_herdr "$ws" "$port" "$owner" "$from" "$dry"
    return
  fi
  if [ "$tab" = 1 ]; then echo "console.sh: not inside herdr; running in the foreground" >&2; fi
  if [ "$dry" = 1 ]; then
    echo "would: record instance.started {port: $port, owner: $owner, from: $from} in $journal"
    echo "would: exec uv run --script $here/dev-console.py ${projects[*]} --port $port --no-live"
    return 0
  fi
  # exec keeps this pid, so the journal's pid is the uv process that `list` and `stop` find by port
  record instance.started "$(jq -nc --argjson port "$port" --arg owner "$owner" --argjson pid "$$" --argjson from "$from" \
    '{port: $port, owner: $owner, pid: $pid, from: $from}')" "$owner"
  echo "dev-console (no live reload, owner $owner): http://127.0.0.1:$port/  (domains of :$from)"
  exec uv run --script "$here/dev-console.py" "${projects[@]}" --port "$port" --no-live
}

cmd_claim() {
  need_jq
  local port="" owner="" pids root
  while [ $# -gt 0 ]; do
    case "$1" in
      --owner) owner="$2"; shift 2 ;;
      *) is_port "$1" || die "unexpected argument: $1"; port="$1"; shift ;;
    esac
  done
  [ -n "$port" ] && [ -n "$owner" ] || die "usage: console.sh claim <port> --owner <name>"
  pids=$(instance_pids "$port") || die "no dev-console instance on port $port"
  read -r root _ <<<"$pids"
  record instance.claimed "$(jq -nc --argjson port "$port" --arg owner "$owner" --argjson pid "$root" \
    '{port: $port, owner: $owner, pid: $pid}')" "$owner"
  echo ":$port is now owned by $owner (pid $root)"
}

# the pid and all its descendants, deepest first, so no child is orphaned by killing its parent
tree() {
  local c
  for c in $(pgrep -P "$1" 2>/dev/null || true); do tree "$c"; done
  echo "$1"
}

cmd_stop() {
  need_jq
  local port="" force=0 pids root pid all
  while [ $# -gt 0 ]; do
    case "$1" in
      --force) force=1; shift ;;
      *) is_port "$1" || die "unexpected argument: $1"; port="$1"; shift ;;
    esac
  done
  [ -n "$port" ] || die "usage: console.sh stop <port> [--force]"
  if [ "$port" = 5057 ] && [ "$force" != 1 ]; then die "5057 is the main instance; pass --force to stop it"; fi
  pids=$(instance_pids "$port") || die "no dev-console instance on port $port"
  read -r root _ <<<"$pids"
  all=$(tree "$root")
  for pid in $all; do kill "$pid" 2>/dev/null || true; done
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    alive "$root" || break
    sleep 0.3
  done
  for pid in $all; do if alive "$pid"; then kill -9 "$pid" 2>/dev/null || true; fi; done
  record instance.stopped "$(jq -nc --argjson port "$port" '{port: $port}')"
  echo "stopped the instance on :$port"
}

# ---------------------------------------------------------------- read

cmd_state() {
  need_jq
  local slug="" port=5057 task="" body code tmp
  while [ $# -gt 0 ]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      --task) task="$2"; shift 2 ;;
      *) slug="$1"; shift ;;
    esac
  done
  [ -n "$slug" ] || die "usage: console.sh state <slug> [--port N] [--task <id>]"
  tmp="$(mktemp)"
  code=$(curl -s --max-time 10 -o "$tmp" -w '%{http_code}' --get "http://127.0.0.1:$port/domain/$slug/state.json" \
    ${task:+--data-urlencode "task=$task"} || true)
  if [ "$code" = 200 ]; then cat "$tmp"; rm -f "$tmp"; return 0; fi
  body=$(cat "$tmp"); rm -f "$tmp"
  case "$code" in
    000) die "nothing answers on port $port" ;;
    404) # a JSON {"error"} comes from the route itself; anything else is a server without the route
      die "port $port: $(echo "$body" | jq -r '.error // empty' 2>/dev/null || true)$(echo "$body" | jq -e .error >/dev/null 2>&1 || echo "no state.json route (older code); see \`console.sh domains $port\`")" ;;
    *) die "port $port answered $code for state.json: ${body:0:200}" ;;
  esac
}

cmd_url() {
  need_jq
  local slug="" port=5057 task="" q="" k v
  while [ $# -gt 0 ]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      --task) task="$2"; shift 2 ;;
      # the page's own query keys (references/console-ui.md, "State in the URL")
      --tab|--ev|--side|--w|--e)
        k="${1#--}"; v=$(jq -rn --arg v "$2" '$v | @uri')
        q="${q:+$q&}$k=$v"; shift 2 ;;
      *) slug="$1"; shift ;;
    esac
  done
  [ -n "$slug" ] || die "usage: console.sh url <slug> [--port N] [--task <id>] [--tab X] [--ev X] [--side X] [--w X] [--e X]"
  # without --task the server redirects /domain/<slug> to the entity it opens, keeping the query
  printf 'http://127.0.0.1:%s/domain/%s%s%s\n' "$port" "$slug" \
    "${task:+/t/$(jq -rn --arg v "$task" '$v | @uri')}" "${q:+?$q}"
}

cmd_actions() {
  need_jq
  local slug="" port=5057 s out
  while [ $# -gt 0 ]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      *) slug="$1"; shift ;;
    esac
  done
  if [ -n "$slug" ]; then set -- "$slug"; else set -- $(domain_rows "$port" | cut -f1); fi
  for s in "$@"; do
    out=$(api "$port" "/api/domains/$s/actions") || die "port $port has no /api/domains/$s/actions (older code, or no such domain)"
    printf '%s: %s\n' "$s" "$(echo "$out" | jq -r 'if length == 0 then "(none)" else join(", ") end')"
  done
}

case "${1:-}" in
  list) shift; cmd_list "$@" ;;
  start) shift; cmd_start "$@" ;;
  stop) shift; cmd_stop "$@" ;;
  claim) shift; cmd_claim "$@" ;;
  domains) shift; cmd_domains "$@" ;;
  state) shift; cmd_state "$@" ;;
  url) shift; cmd_url "$@" ;;
  actions) shift; cmd_actions "$@" ;;
  *) echo "usage: console.sh list | start [port] --owner <n> [--from 5057] [--no-tab] [--dry-run] | stop <port> [--force] | claim <port> --owner <n> | domains [port] | domains add <path> | domains remove <path|slug> | state <slug> | url <slug> | actions [<slug>]" >&2; exit 2 ;;
esac
