#!/usr/bin/env bash
# run.sh: processo longo (servidor, watcher, suite de testes) numa sessao tmux nomeada, presa ao dono (a worktree).
# Nunca como processo solto. Sessoes criadas aqui levam a opcao @procs=1 e @owner=<pasta>; so elas sao mexidas.
# Log em $PROCS_DIR/<sessao>/<nome>.log (PROCS_DIR padrao ~/.local/state/procs). Saida: 0 ok, 1 erro, 2 uso.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/lib.sh"
SELF="$HERE/run.sh"
PROCS_DIR="${PROCS_DIR:-$HOME/.local/state/procs}"
PROCS_MAX_SLOTS="${PROCS_MAX_SLOTS:-2}"
LABEL=com.biliboss.procs-reaper

usage() {
  cat >&2 <<'U'
uso:
  run.sh start <nome> [--cwd DIR] [--owner DIR] [--low] [--slot] [--restart] -- <comando...>
  run.sh ls [--json]
  run.sh log <sessao>:<nome> [N=40]
  run.sh stop <sessao>[:<nome>]      (ou: stop --owner DIR)
  run.sh reap [--dry-run]
  run.sh install-reaper [--print] [--no-load] | uninstall-reaper [--no-load]
U
  exit 2
}

# sanitize: so [A-Za-z0-9_-] (sem ponto nem dois-pontos, que o tmux le como alvo)
sanitize() { printf '%s' "$1" | tr -c 'A-Za-z0-9_-' '-'; }
physdir() { (cd "$1" 2>/dev/null && pwd -P); }
now_iso() { date '+%Y-%m-%dT%H:%M:%S%z'; }

# ---------- slots: tampa global de execucoes (mkdir atomico) ----------
slot_acquire() { # imprime o numero do slot em SLOT_HELD
  local root="$PROCS_DIR/slots" i d pid age
  mkdir -p "$root"
  while :; do
    i=1
    while [ "$i" -le "$PROCS_MAX_SLOTS" ]; do
      d="$root/$i.lock"
      if mkdir "$d" 2>/dev/null; then
        printf '%s\n' "$$" > "$d/pid"; SLOT_HELD=$d; return 0
      fi
      pid=$(cat "$d/pid" 2>/dev/null)
      if [ -n "$pid" ]; then
        kill -0 "$pid" 2>/dev/null || slot_reclaim "$d"
      else   # lock sem pid: dono morreu entre mkdir e escrita (> 10 s) ou esta escrevendo
        age=$(( $(date +%s) - $(stat -f %m "$d" 2>/dev/null || echo 0) ))
        [ "$age" -gt 10 ] && slot_reclaim "$d"
      fi
      i=$((i+1))
    done
    sleep 0.5
  done
}
slot_reclaim() { # mv atomico: so um disputante leva o lock velho
  local d=$1 tmp="$1.stale.$$"
  mv "$d" "$tmp" 2>/dev/null && rm -rf -- "$tmp"
}
slot_release() { [ -n "${SLOT_HELD:-}" ] && rm -rf -- "$SLOT_HELD"; SLOT_HELD=""; }

# ---------- _exec: roda dentro do pane (interno) ----------
cmd_exec() {
  local log=$1 slot=$2 low=$3; shift 3
  [ "${1:-}" = -- ] && shift
  SLOT_HELD=""
  trap slot_release EXIT
  setst() { [ -n "${TMUX_PANE:-}" ] && tm set-option -w -t "$TMUX_PANE" "$1" "$2" >/dev/null 2>&1; return 0; }
  mkdir -p "$(dirname "$log")"
  local pre=""
  if [ "$low" = 1 ]; then
    if [ -n "${PROCS_TASKPOLICY:-}" ] || command -v taskpolicy >/dev/null 2>&1; then
      pre="${PROCS_TASKPOLICY:-$(command -v taskpolicy)} -b"
    else pre="nice -n 10"; fi
  fi
  { printf '== %s | cwd=%s | slot=%s low=%s | cmd=%s\n' "$(now_iso)" "$PWD" "$slot" "${pre:-no}" "$*"; } >> "$log"
  if [ "$slot" = 1 ]; then
    setst @state waiting
    printf '[run.sh] esperando vaga (max %s)...\n' "$PROCS_MAX_SLOTS" | tee -a "$log"
    slot_acquire
  fi
  setst @state running
  # shellcheck disable=SC2086
  $pre "$@" 2>&1 | tee -a "$log"
  local rc=${PIPESTATUS[0]}
  slot_release
  printf 'exit=%s\n' "$rc" >> "$log"
  setst @exit "$rc"; setst @state exited
  printf '\n[run.sh] terminou: exit=%s  (Enter fecha esta janela)\n' "$rc"
  read -r _ || sleep 86400
  return "$rc"
}

# ---------- helpers de sessao ----------
tagged_sessions() { # linhas: nome|owner (so as com @procs=1)
  tm list-sessions -F '#{session_name}|#{@procs}|#{@owner}' 2>/dev/null | awk -F'|' '$2=="1"{o=$3;for(i=4;i<=NF;i++)o=o "|" $i; print $1 "|" o}'
}
is_tagged() { [ "$(tm show-options -v -t "=$1:" @procs 2>/dev/null)" = 1 ]; }
has_session() { tm has-session -t "=$1" 2>/dev/null; }
owner_alive() { [ -n "$1" ] && [ -d "$1" ]; }  # the owner folder exists (a removed worktree takes its folder with it; a non-git --owner counts too)

# ---------- start ----------
cmd_start() {
  [ $# -ge 1 ] || usage
  local name=$1 cwd=$PWD owner="" low=0 slot=0 restart=0; shift
  while [ $# -gt 0 ]; do
    case $1 in
      --cwd) [ $# -ge 2 ] || usage; cwd=$2; shift ;;
      --owner) [ $# -ge 2 ] || usage; owner=$2; shift ;;
      --low) low=1 ;;
      --slot) slot=1 ;;
      --restart) restart=1 ;;
      --) shift; break ;;
      *) die "opcao desconhecida: $1 (o comando vem depois de --)" ;;
    esac; shift
  done
  [ $# -ge 1 ] || { DIE_CODE=2; die "faltou o comando depois de --"; }
  [ -n "$name" ] || die "nome vazio"
  [ -d "$cwd" ] || die "diretorio nao existe: $cwd"
  cwd=$(physdir "$cwd")
  if [ -z "$owner" ]; then
    owner=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || die "$cwd nao esta num repo git: passe --owner DIR"
  fi
  [ -d "$owner" ] || die "owner nao existe: $owner"
  owner=$(physdir "$owner")
  local sess wn log
  sess=$(sanitize "$(basename "$owner")"); wn=$(sanitize "$name")
  [ -n "$sess" ] && [ -n "$wn" ] || die "nome ou dono invalido"
  log="$PROCS_DIR/$sess/$wn.log"
  mkdir -p "$PROCS_DIR/$sess" || die "nao criei $PROCS_DIR/$sess"
  local runner=(env "PROCS_DIR=$PROCS_DIR" "PROCS_MAX_SLOTS=$PROCS_MAX_SLOTS" "TMUX_BIN=$TMUX_BIN" "TMUX_SOCKET=${TMUX_SOCKET:-}"
    ${PROCS_TASKPOLICY:+"PROCS_TASKPOLICY=$PROCS_TASKPOLICY"} /bin/bash "$SELF" _exec "$log" "$slot" "$low" -- "$@")
  local pid
  if has_session "$sess"; then
    is_tagged "$sess" || die "a sessao \"$sess\" existe e nao foi criada pelo run.sh: nao mexo nela"
    local o; o=$(tm show-options -v -t "=$sess:" @owner 2>/dev/null)
    [ "$o" = "$owner" ] || die "a sessao \"$sess\" e de outro dono ($o); mesmo nome de pasta. Use outra pasta de worktree"
    local row wid wst
    row=$(tm list-windows -t "=$sess" -F '#{window_id}|#{@state}|#{window_name}' | awk -F'|' -v n="$wn" '{w=$3;for(i=4;i<=NF;i++)w=w "|" $i} w==n{print $1 "|" $2; exit}')
    if [ -n "$row" ]; then
      wid=${row%%|*}; wst=${row#*|}
      if [ "$wst" != exited ] && [ "$restart" = 0 ]; then
        die "ja roda \"$wn\" na sessao $sess (estado: ${wst:-starting}). Use --restart, ou 'run.sh log $sess:$wn'"
      fi
      # respawn no lugar: mata o processo velho e reusa a janela (matar a unica janela derrubaria a sessao)
      tm set-option -w -u -t "$wid" @exit >/dev/null 2>&1; tm set-option -w -t "$wid" @state starting >/dev/null
      pid=$(tm respawn-pane -k -t "$wid" -c "$cwd" "${runner[@]}" >/dev/null && tm display-message -p -t "$wid" '#{pane_id}') || die "respawn-pane falhou"
    fi
    [ -n "${pid:-}" ] || pid=$(tm new-window -d -P -F '#{pane_id}' -t "=$sess:" -n "$wn" -c "$cwd" "${runner[@]}") || die "new-window falhou"
  else
    pid=$(tm new-session -d -P -F '#{pane_id}' -s "$sess" -n "$wn" -c "$cwd" "${runner[@]}") || die "new-session falhou"
    tm set-option -t "=$sess:" @procs 1 >/dev/null
    tm set-option -t "=$sess:" @owner "$owner" >/dev/null
  fi
  tm set-option -w -t "$pid" @log "$log" >/dev/null
  tm set-option -w -t "$pid" @cmd "$*" >/dev/null
  printf '%s:%s  pane=%s  log=%s\n' "$sess" "$wn" "$pid" "$log"
}

# ---------- ls ----------
cmd_ls() {
  local json=0; [ "${1:-}" = --json ] && json=1
  local tsv="" s o ex
  while IFS='|' read -r s o; do
    [ -n "$s" ] || continue
    owner_alive "$o" && ex=yes || ex=no
    local w
    w=$(tm list-windows -t "=$s" -F '#{window_name}|#{@state}|#{@exit}|#{@log}|#{@cmd}' 2>/dev/null)
    local wname st rc lg cm
    while IFS='|' read -r wname st rc lg cm; do
      [ -n "$wname" ] || continue
      [ -n "$st" ] || st=starting
      tsv="$tsv$s|$o|$ex|$wname|$st|$rc|$lg|$cm
"
    done <<EOF
$w
EOF
  done <<EOF
$(tagged_sessions)
EOF
  if [ "$json" = 1 ]; then
    printf '%s' "$tsv" | awk -F'|' 'function e(x){gsub(/\\/,"\\\\",x);gsub(/"/,"\\\"",x);gsub(/\t/,"\\t",x);return x}
      BEGIN{printf "["} NF>=7{c=$8;for(i=9;i<=NF;i++)c=c "|" $i
      printf "%s{\"session\":\"%s\",\"owner\":\"%s\",\"owner_exists\":%s,\"window\":\"%s\",\"state\":\"%s\",\"exit\":%s,\"log\":\"%s\",\"cmd\":\"%s\"}",
        (n++?",":""),e($1),e($2),($3=="yes"?"true":"false"),e($4),e($5),($6==""?"null":$6),e($7),e(c)}
      END{print "]"}'
    return 0
  fi
  { printf 'SESSION|OWNER|OWNER?|WINDOW|STATE|EXIT|LOG|CMD\n'; printf '%s' "$tsv"; } | column -t -s '|'
}

# ---------- log ----------
cmd_log() {
  [ $# -ge 1 ] || usage
  local t=$1 n=${2:-40}
  case $n in ''|*[!0-9]*) die "N invalido: $n" ;; esac
  case $t in *:*) ;; *) die "use <sessao>:<nome>" ;; esac
  local f="$PROCS_DIR/$(sanitize "${t%%:*}")/$(sanitize "${t#*:}").log"
  [ -f "$f" ] || die "sem log: $f"
  tail -n "$n" "$f"
}

# ---------- stop ----------
cmd_stop() {
  [ $# -ge 1 ] || usage
  local t=$1 sess wn=""
  if [ "$t" = --owner ]; then
    [ $# -ge 2 ] || usage
    sess=$(sanitize "$(basename "$2")")
    # a pasta pode ja nao existir (hook post-remove): vale o nome
    has_session "$sess" || { printf 'nada a parar para %s\n' "$sess"; return 0; }
    local o; o=$(tm show-options -v -t "=$sess:" @owner 2>/dev/null)
    if owner_alive "$o" && [ "$o" != "$2" ] && [ "$o" != "$(physdir "$2")" ]; then die "a sessao $sess e de outro dono ($o)"; fi
  else
    sess=${t%%:*}; [ "$sess" = "$t" ] || wn=$(sanitize "${t#*:}")
    has_session "$sess" || die "sessao inexistente: $sess"
  fi
  is_tagged "$sess" || die "a sessao \"$sess\" nao foi criada pelo run.sh: recuso"
  if [ -n "$wn" ]; then
    local wid
    wid=$(tm list-windows -t "=$sess" -F '#{window_id}|#{window_name}' | awk -F'|' -v n="$wn" '{w=$2;for(i=3;i<=NF;i++)w=w "|" $i} w==n{print $1; exit}')
    [ -n "$wid" ] || die "sem janela \"$wn\" na sessao $sess"
    tm kill-window -t "$wid" || die "kill-window falhou"
    printf 'janela %s:%s parada\n' "$sess" "$wn"
  else
    tm kill-session -t "=$sess" || die "kill-session falhou"
    printf 'sessao %s parada\n' "$sess"
  fi
}

# ---------- reap ----------
cmd_reap() {
  local dry=0; [ "${1:-}" = --dry-run ] && dry=1
  local s o n=0
  while IFS='|' read -r s o; do
    [ -n "$s" ] || continue
    if ! owner_alive "$o"; then
      n=$((n+1))
      if [ "$dry" = 1 ]; then printf 'mataria %s (dono sumiu: %s)\n' "$s" "$o"
      else tm kill-session -t "=$s" >/dev/null 2>&1 && printf 'matei %s (dono sumiu: %s)\n' "$s" "$o"; fi
    fi
  done <<EOF
$(tagged_sessions)
EOF
  [ "$n" -gt 0 ] || printf 'nada a limpar\n'
}

# ---------- launchd ----------
plist_text() {
  local bindir=$1
  cat <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$bindir/run.sh</string>
    <string>reap</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TMUX_BIN</key><string>$TMUX_BIN</string>
    <key>PROCS_DIR</key><string>$PROCS_DIR</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartInterval</key><integer>60</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$PROCS_DIR/reaper.log</string>
  <key>StandardErrorPath</key><string>$PROCS_DIR/reaper.log</string>
</dict>
</plist>
P
}

cmd_install_reaper() {
  local print=0 load=1
  while [ $# -gt 0 ]; do case $1 in --print) print=1 ;; --no-load) load=0 ;; *) usage ;; esac; shift; done
  # copia estavel: o caminho do plugin muda a cada versao e a antiga some
  local bindir="${PROCS_BIN_DIR:-$HOME/.local/share/procs/bin}"
  local plist="$HOME/Library/LaunchAgents/$LABEL.plist"
  if [ "$print" = 1 ]; then plist_text "$bindir"; return 0; fi
  mkdir -p "$bindir" "$PROCS_DIR" "$HOME/Library/LaunchAgents" || die "mkdir falhou"
  cp "$HERE/run.sh" "$HERE/lib.sh" "$bindir/" || die "copia falhou"
  chmod +x "$bindir/run.sh"
  plist_text "$bindir" > "$plist.tmp" && mv "$plist.tmp" "$plist"
  if [ "$load" = 1 ]; then
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1
    launchctl bootstrap "gui/$(id -u)" "$plist" || die "launchctl bootstrap falhou"
  fi
  printf 'reaper instalado: %s (copia em %s)\n' "$plist" "$bindir"
}

cmd_uninstall_reaper() {
  local load=1; [ "${1:-}" = --no-load ] && load=0
  local plist="$HOME/Library/LaunchAgents/$LABEL.plist"
  [ "$load" = 1 ] && launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1
  rm -f -- "$plist"
  printf 'reaper removido\n'
}

[ $# -ge 1 ] || usage
sub=$1; shift
case $sub in
  start) cmd_start "$@" ;;
  ls) cmd_ls "$@" ;;
  log) cmd_log "$@" ;;
  stop) cmd_stop "$@" ;;
  reap) cmd_reap "$@" ;;
  install-reaper) cmd_install_reaper "$@" ;;
  uninstall-reaper) cmd_uninstall_reaper "$@" ;;
  _exec) cmd_exec "$@" ;;
  *) usage ;;
esac
