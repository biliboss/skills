#!/usr/bin/env bash
# handoff.sh: the shift handover of a Hermes agent in tmux. The session that ran long hands its state over: it is
# logged, branched into a tab right of the agent's, and only then the agent's own tab starts clean (/new) with a
# short summary of where everything went. Nothing is cleaned unless the copy is up.
#
#   handoff.sh [<tmux target>] [--from ID] [--detach]   the handoff (target default: $TMUX_PANE, the caller's pane)
#   handoff.sh log [N]                                  the last N handed-over sessions, with the resume command
#
# Env: HANDOFF_LOG (default ~/.local/state/bili-sessions.jsonl), HANDOFF_IDLE_TIMEOUT (s, default 600),
#      HANDOFF_READY_TIMEOUT (s, default 60), TMUX_SOCKET (private server, tests), TMUX_BIN, HERMES_BIN, HERMES_PY,
#      THREAD_FORK (fork command, tests), THREAD_SH (for the thread() Value Object), HANDOFF_PROFILE (default bili).
set -uo pipefail

TMUX_BIN="${TMUX_BIN:-$(type -P tmux || echo tmux)}"
HERMES_BIN="${HERMES_BIN:-$(type -P hermes || true)}"
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
THREAD_SH="${THREAD_SH:-$HERE/../../thread/scripts/thread.sh}"
LOG="${HANDOFF_LOG:-$HOME/.local/state/bili-sessions.jsonl}"
IDLE_TIMEOUT="${HANDOFF_IDLE_TIMEOUT:-600}"
READY_TIMEOUT="${HANDOFF_READY_TIMEOUT:-60}"
PROFILE="${HANDOFF_PROFILE:-bili}"

tm() { if [ -n "${TMUX_SOCKET:-}" ]; then "$TMUX_BIN" -L "$TMUX_SOCKET" "$@"; else "$TMUX_BIN" "$@"; fi; }
die() { echo "handoff.sh: $*" >&2; exit 1; }
say() { echo "handoff: $*"; }
eval "$(sed -n '/^thread() {/,/^}/p' "$THREAD_SH")"   # the thread Value Object: one name rule for tabs
type thread >/dev/null 2>&1 || die "cannot load thread() from $THREAD_SH"

# --- the pane's state, read from the Hermes status bar ------------------------------------------------------------
screen() { tm capture-pane -p -t "$1" 2>/dev/null | grep -v '^[[:space:]]*$'; }
is_ready() { screen "$1" | tail -3 | grep -q 'ready'; }   # idle: the bar says "ready"; mid-turn it says "analyzing…"
context_of() { screen "$1" | grep -oE '[0-9.]+k/[0-9.]+[MK]' | tail -1; }
wait_until() { # pane seconds -> 0 when ready within the time
  local deadline=$((SECONDS + $2))
  while [ "$SECONDS" -lt "$deadline" ]; do is_ready "$1" && return 0; sleep 1; done
  return 1
}

hermes_py() { # the interpreter the `hermes` launcher execs (fork.py needs Hermes's own dependencies)
  [ -z "${HERMES_PY:-}" ] || { printf '%s' "$HERMES_PY"; return; }
  grep -o '/[^ ]*/python3[^ ]*' "$(readlink -f "$HERMES_BIN")" 2>/dev/null | head -1 && return
  local inner; inner="$(grep -o '/[^ "]*/hermes' "$HERMES_BIN" 2>/dev/null | head -1)"
  [ -n "$inner" ] && grep -o '/[^ ]*/python3[^ ]*' "$inner" 2>/dev/null | head -1
}
fork() { # source title -> new id
  if [ -n "${THREAD_FORK:-}" ]; then $THREAD_FORK "$1" "$2" --profile "$PROFILE"; return; fi
  local py; py="$(hermes_py)"; [ -n "$py" ] || { echo "no Hermes python (set HERMES_PY)" >&2; return 1; }
  "$py" -I "$(dirname "$THREAD_SH")/fork.py" "$1" "$2" --profile "$PROFILE"
}
last_message() { # session id -> the last user prompt, one line, max 160 chars (best effort)
  "$HERMES_BIN" -p "$PROFILE" sessions export --session-id "$1" --only user-prompts --format jsonl - 2>/dev/null |
    tail -1 | jq -r '(.content // .text // .message // "") | tostring' 2>/dev/null | tr '\n' ' ' | cut -c1-160
}

cmd_log() {
  [ -f "$LOG" ] || { echo "nenhuma passagem ainda ($LOG)"; return 0; }
  tail -n "${1:-10}" "$LOG" | jq -r --arg p "$PROFILE" \
    '"\(.at)  \(.title)  [\(.context // "?")]  \(.session_id)\n    \(.last_message // "" | .[0:100])\n    hermes -p \($p) --resume \(.session_id)"'
}

cmd_handoff() {
  local target="${TMUX_PANE:-}" from="" detach=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --from) from="${2:?--from ID}"; shift ;;
      --detach) detach=1 ;;
      -*) die "unknown option: $1" ;;
      *) target="$1" ;;
    esac; shift
  done
  [ -n "$target" ] || die "no target: pass a tmux target (the agent's pane) or run inside tmux"
  # ids only from here on: a session name with a dot is read by tmux as a pane separator
  local info pane win name cwd
  info="$(tm display-message -p -t "$target" '#{pane_id}|#{window_id}|#{window_name}|#{pane_current_path}')" \
    || die "no such tmux target: $target"
  IFS='|' read -r pane win name cwd <<<"$info"
  [ -n "$from" ] || from="$(tm show-options -wqv -t "$win" @hsid 2>/dev/null)"
  [ -n "$from" ] || { [ "$pane" = "${TMUX_PANE:-}" ] && from="${HERMES_SESSION_ID:-}"; }
  [ -n "$from" ] || die "which Hermes session runs in $pane? pass --from <session id> (nothing was changed)"
  # the caller handing ITSELF over: its turn only ends after this script returns, so the rest runs detached
  if [ "$detach" = 0 ] && [ "$pane" = "${TMUX_PANE:-}" ]; then detach=1; fi

  # 1. log first: whatever happens next, the session can be found and resumed
  local title ctx last at
  title="$(thread "$name")"; ctx="$(context_of "$pane")"; last="$(last_message "$from")"
  at="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  mkdir -p "$(dirname "$LOG")"
  jq -cn --arg at "$at" --arg id "$from" --arg t "$title" --arg c "$ctx" --arg m "$last" --arg tg "$pane $win" \
    '{at:$at, session_id:$id, title:$t, context:(if $c=="" then null else $c end), last_message:(if $m=="" then null else $m end), tmux:$tg}' >>"$LOG"
  say "registrado em $LOG: $title [${ctx:-?}] $from"

  if [ "$detach" = 1 ]; then
    local dl="${LOG%.jsonl}.handoff.log"
    nohup "$0" _rest "$pane" "$win" "$name" "$cwd" "$from" >>"$dl" 2>&1 </dev/null &
    say "o resto roda em segundo plano quando o turno acabar (log: $dl)"
    return 0
  fi
  cmd_rest "$pane" "$win" "$name" "$cwd" "$from"
}

cmd_rest() { # pane win name cwd source-id: wait idle, branch, then clean
  local pane="$1" win="$2" name="$3" cwd="$4" from="$5"
  # 4. the lock: mid-turn nothing is touched; wait for the turn to end, at most IDLE_TIMEOUT
  wait_until "$pane" "$IDLE_TIMEOUT" || die "o agente em $pane não ficou ocioso em ${IDLE_TIMEOUT}s: nada foi limpo (só o log)"

  # 2. the branch: an offline copy, opened right of the agent's tab, in the background (the focus is not ours)
  local tab newid copy
  tab="$(thread "$name antes")"
  newid="$(fork "$from" "$tab")" && [ -n "$newid" ] || die "o fork de $from falhou: nada foi limpo (só o log)"
  copy="$(tm new-window -a -d -P -F '#{pane_id}' -t "$win" -n "$tab" -c "$cwd" \
    "$(printf '%q -p %q --resume %q' "$HERMES_BIN" "$PROFILE" "$newid")")" || die "a aba do branch não abriu: nada foi limpo"
  local cwin; cwin="$(tm display-message -p -t "$copy" '#{window_id}')"
  tm set-option -w -t "$cwin" automatic-rename off; tm set-option -w -t "$cwin" @hsid "$newid"
  wait_until "$copy" "$READY_TIMEOUT" || die "o branch $newid não ficou pronto em ${READY_TIMEOUT}s: a original não foi limpa"
  say "branch $newid aberto na aba '$tab' ($cwin)"

  # 3. clean the original only now: /new, then the short summary as one message
  is_ready "$pane" || die "o agente voltou a trabalhar: a original não foi limpa (o branch fica aberto)"
  tm send-keys -t "$pane" C-u
  tm send-keys -t "$pane" -l "/new"; sleep 0.3; tm send-keys -t "$pane" Enter
  wait_until "$pane" "$READY_TIMEOUT" || true
  sleep 1
  printf '%s\n' \
    "Passagem de turno (handoff): esta aba começou do zero." \
    "A conversa anterior ($from) continua no branch $newid, na aba '$tab', logo à direita." \
    "Registro: $LOG (handoff.sh log). Retomar: hermes -p $PROFILE --resume $newid" \
    "Leia o plano (~/.local/state/plano-mesa.md) antes de continuar." |
    tm load-buffer -b "handoff-$$" -
  tm paste-buffer -p -d -b "handoff-$$" -t "$pane"; sleep 0.3; tm send-keys -t "$pane" Enter
  tm set-option -w -u -t "$win" @hsid 2>/dev/null || true   # the old id now lives in the copy
  say "a aba original começou do zero; resumo enviado"
}

case "${1:-}" in
  log) shift; cmd_log "$@" ;;
  _rest) shift; cmd_rest "$@" ;;
  -h|--help|help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
  *) cmd_handoff "$@" ;;
esac
