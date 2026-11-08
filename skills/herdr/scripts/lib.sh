#!/usr/bin/env bash
# lib.sh - shared helpers for the herdr scripts. Source it; do not run it.
# Every script does:  . "$(dirname "$0")/lib.sh"; hl_parse "$@"; set -- "${ARGS[@]}"
# Provides: argument parsing (-h -n --json --yes), error helpers, the herdr-app/hc wrappers that
# map errors to the exit contract, and hl_op, the one wrapper every state-changing script uses to
# log <script>.start and <script>.end through the logging skill.
# Exit contract: 0 ok, 1 not found/failed, 2 usage, 3 timeout, 4 blocked on permission,
# 5 operation done but the end log failed.
# Bash 3.2 and BSD tools only. No set -u (empty arrays are unbound in 3.2).

SCRIPT=$(basename "$0" .sh)
HERE=$(cd "$(dirname "$0")" && pwd)

hl_usage() { awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"; }
hl_die() { local c=$1; shift; echo "$SCRIPT: $*" >&2; exit "$c"; }
hl_usage_err() { echo "$SCRIPT: $*" >&2; hl_usage >&2; exit 2; }
hl_need() { local c; for c in "$@"; do command -v "$c" >/dev/null 2>&1 || hl_die 1 "requirement missing: $c"; done; }

# hl_parse "$@": strips -h, -n, --json, --yes anywhere before a literal "--"; the rest lands in ARGS
# (a "--" and everything after it stay verbatim).
hl_parse() {
  DRY=0; JSON=0; YES=0; ARGS=(); OUT=
  while [ $# -gt 0 ]; do
    case $1 in
      -h|--help) hl_usage; exit 0;;
      -n) DRY=1;;
      --json) JSON=1;;
      --yes) YES=1;;
      --) ARGS+=("$@"); break;;
      *) ARGS+=("$1");;
    esac
    shift
  done
}

# hl_text VALUE: VALUE itself, or all of stdin when VALUE is "-".
hl_text() { if [ "$1" = "-" ]; then cat; else printf '%s' "$1"; fi; }
hl_name() { case $1 in *[!a-z0-9_-]*|'') return 1;; esac; [ ${#1} -le 32 ]; }

# hl_obj k=v k:=json ...: a JSON object ("k=v" is a string, "k:=json" is raw JSON).
hl_obj() {
  local o='{}' kv k
  for kv in "$@"; do
    k=${kv%%=*}
    case $k in
      *:) k=${k%:}; o=$(jq -c --arg k "$k" --argjson v "${kv#*=}" '.[$k]=$v' <<<"$o") || return 1;;
      *) o=$(jq -c --arg k "$k" --arg v "${kv#*=}" '.[$k]=$v' <<<"$o") || return 1;;
    esac
  done
  printf '%s' "$o"
}

# hl_kv "allowed keys" "required keys" "$@": parses --key value pairs into OBJARGS (for hl_obj)
# and TASKLEN (length of --task). --task accepts "-" for stdin; --argv must be a JSON array.
hl_kv() {
  local allowed=" $1 " required=$2 seen=" " k v r; shift 2; OBJARGS=(); TASKLEN=0
  while [ $# -gt 0 ]; do
    case $1 in --*) k=${1#--};; *) hl_usage_err "unexpected '$1'";; esac
    case $allowed in *" $k "*) ;; *) hl_usage_err "unknown option --$k";; esac
    [ $# -ge 2 ] || hl_usage_err "--$k needs a value"
    v=$2; shift 2; seen="$seen$k "
    case $k in
      task) v=$(hl_text "$v"); TASKLEN=${#v}; OBJARGS+=("task=$v");;
      argv) printf '%s' "$v" | jq -e 'type=="array"' >/dev/null 2>&1 || hl_usage_err "--argv wants a JSON array"
            OBJARGS+=("argv:=$v");;
      *) OBJARGS+=("$k=$v");;
    esac
  done
  for r in $required; do case $seen in *" $r "*) ;; *) hl_usage_err "--$r is required";; esac; done
}

# hl_where: JSON {terminal,pane,status,app,tab,tab_name,space,space_name} for $HC_TERMINAL_ID, else rc 1.
hl_where() {
  local ls
  [ -n "${HC_TERMINAL_ID:-}" ] || { echo "$SCRIPT: HC_TERMINAL_ID is empty: not inside an hc terminal" >&2; return 1; }
  ls=$(herdr-app ls) || { echo "$SCRIPT: herdr-app ls failed: is the window open?" >&2; return 1; }
  jq -ce --arg t "$HC_TERMINAL_ID" '[.spaces[] as $s | $s.tabs[] as $b | $b.terminals[]
    | select(.terminal == $t)
    | {terminal, pane, status, app, tab: $b.id, tab_name: $b.name, space: $s.id, space_name: $s.name}][0] // empty' <<<"$ls" \
    | grep . || { echo "$SCRIPT: $HC_TERMINAL_ID is not shown in the window" >&2; return 1; }
}

# hl_exists space|tab|pane ID: is that id in the window right now?
hl_exists() {
  local p
  case $1 in space) p='.spaces[]|.id';; tab) p='.spaces[].tabs[]|.id';; pane) p='.spaces[].tabs[].terminals[]|.pane';; *) return 1;; esac
  herdr-app ls | jq -e --arg i "$2" "any($p; . == \$i)" >/dev/null 2>&1
}

# hl_app_do COMMAND JSON_OBJECT: herdr-app do; an {"error":...} reply or non-zero exit goes to stderr, rc 1.
hl_app_do() {
  local o rc
  o=$(herdr-app do "$@" 2>&1); rc=$?
  if [ $rc -ne 0 ] || jq -e 'type == "object" and has("error")' >/dev/null 2>&1 <<<"$o"; then
    printf '%s\n' "$o" >&2; return 1
  fi
  printf '%s\n' "$o"
}

# hl_hc ARGS...: hc, with its exit mapped to the contract (9 blocked -> 4, 124 timeout -> 3, other -> 1).
hl_hc() { hc "$@"; case $? in 0) return 0;; 9) return 4;; 124) return 3;; *) return 1;; esac; }

# hl_wait_rc WAITRESULT_JSON: 4 if it or a child is blocked, 1 on error, not_started or a program that exited
# non-zero (its own code is not propagated: 3/4/5 mean other things), 3 on timeout, else 0. No exit_code -> 0.
hl_wait_rc() {
  jq -r '([.] + (.children // [])) as $all
    | if any($all[]; .status == "blocked") then 4
      elif .reason == "not_started" or any($all[]; .status == "error") then 1
      elif .ended == false or .reason == "timeout" then 3
      elif any($all[]; (.exit_code // 0) != 0) then 1 else 0 end' <<<"$1"
}

# hl_print: OUT as key<TAB>value rows, or raw with --json (or when it is not a JSON object).
hl_print() {
  if [ "$JSON" = 1 ]; then printf '%s\n' "$OUT"; return; fi
  jq -r 'if type == "object" then to_entries[] | [.key, (.value | if type == "string" then . else tojson end)] | @tsv
         else tostring end' <<<"$OUT" 2>/dev/null || printf '%s\n' "$OUT"
}

hl_show() {
  case $1 in hl_app_do) shift; set -- herdr-app do "$@";; hl_hc) shift; set -- hc "$@";; esac
  local a out=
  for a in "$@"; do
    case $a in
      ''|*[!A-Za-z0-9_@%+=:,./-]*) a="'$(printf '%s' "$a" | sed "s/'/'\\\\''/g")'";;
    esac
    out="$out$a "
  done
  printf '%s\n' "${out% }"
}
hl_ms() { perl -MTime::HiRes=time -e 'printf "%d", time*1000' 2>/dev/null || echo $(( $(date +%s) * 1000 )); }

# hl_discover: sets LOGGING_EMIT (env first; else the one LOGGING_EMIT=... line of $BILIBOSS_ENV,
# read as text: the file is not sourced, so nothing in it runs or is exported) and checks it is executable.
hl_discover() {
  local f v
  if [ -z "${LOGGING_EMIT:-}" ]; then
    f=${BILIBOSS_ENV:-$HOME/.config/biliboss/.env}
    if [ -r "$f" ]; then
      v=$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}LOGGING_EMIT=//p' "$f" | tail -1)
      v=${v%% #*}; v=${v%"${v##*[![:space:]]}"}; v=${v#[\"\']}; v=${v%[\"\']}
      case $v in '$HOME/'*) v=$HOME/${v#\$HOME/};; '${HOME}/'*) v=$HOME/${v#\$\{HOME\}/};; '~/'*) v=$HOME/${v#\~/};; esac
      LOGGING_EMIT=$v
    fi
  fi
  if [ -z "${LOGGING_EMIT:-}" ] || [ ! -x "$LOGGING_EMIT" ]; then
    echo "$SCRIPT: logging is not configured: set LOGGING_EMIT to the logging skill's scripts/emit.sh (environment, or a LOGGING_EMIT= line in ${f:-${BILIBOSS_ENV:-$HOME/.config/biliboss/.env}})" >&2
    return 1
  fi
}

# hl_op TARGET TEXTLEN CMD...: the one path for state changes. Dry run (-n) prints the command (or
# HL_DRYTXT) and does nothing. Otherwise: discover logging, emit <script>.start (failure -> rc 1,
# CMD does NOT run), run CMD (stdout kept in OUT), emit <script>.end with exit_code and duration_ms
# (failure -> warn, rc 5 if CMD succeeded). HL_EXTRA=(k=v ...) adds attributes. Only lengths are logged.
hl_op() {
  local target=$1 tlen=$2 trace t0 rc at sev=INFO; shift 2
  if [ "$DRY" = 1 ]; then if [ -n "${HL_DRYTXT:-}" ]; then printf '%s\n' "$HL_DRYTXT"; else hl_show "$@"; fi; OUT=; return 0; fi
  hl_discover || return 1
  trace=$("$LOGGING_EMIT" --trace-id) || { echo "$SCRIPT: logging failed, not running" >&2; return 1; }
  at=(target="$target" caller="${HC_TERMINAL_ID:-}"); [ "$tlen" = "-" ] || at+=(text_len="$tlen")
  at+=("${HL_EXTRA[@]}")
  LOGGING_TRACE_ID=$trace "$LOGGING_EMIT" herdr "$SCRIPT.start" "${at[@]}" \
    || { echo "$SCRIPT: start log failed, not running" >&2; return 1; }
  t0=$(hl_ms)
  OUT=$("$@" < "${HL_IN:-/dev/null}"); rc=$?
  [ $rc -eq 0 ] || sev=ERROR
  LOGGING_TRACE_ID=$trace "$LOGGING_EMIT" --severity $sev herdr "$SCRIPT.end" "${at[@]}" exit_code=$rc duration_ms=$(( $(hl_ms) - t0 )) \
    || { echo "$SCRIPT: warning: operation finished (exit $rc) but the end log failed" >&2; [ $rc -eq 0 ] && return 5; }
  return $rc
}
