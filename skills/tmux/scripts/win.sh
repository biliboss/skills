#!/usr/bin/env bash
# win.sh: listar, abrir e renomear janelas do tmux. Nenhum comando aqui mata sessao ou servidor.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/lib.sh"

usage() {
  cat >&2 <<'U'
uso:
  win.sh list [--json]
  win.sh new <nome> <comando> [--cwd DIR] [--session S] [--allow-duplicate]
  win.sh rename <alvo> <novo-nome>
U
  exit 2
}

cmd_list() {
  local json=0
  [ "${1:-}" = "--json" ] && json=1
  local rows; rows=$(tm list-panes -a -F "$PANE_FMT" 2>&1) || die "tmux sem servidor ou com erro: $rows"
  if [ "$json" = 1 ]; then
    if command -v jq >/dev/null 2>&1; then
      printf '%s\n' "$rows" | jq -R -s '[split("\n")[] | select(length>0) | split("|") | {
        pane_id: .[0], session: .[1], window_index: (.[2]|tonumber), pane_index: (.[3]|tonumber),
        active: (.[4]=="1" and .[5]=="1"), command: .[6], cwd: .[7], window: (.[8:]|join("|"))}]'
    else
      printf '%s\n' "$rows" | awk -F'|' 'function e(s){gsub(/\\/,"\\\\",s);gsub(/"/,"\\\"",s);return s}
        BEGIN{printf "["} {n=$9;for(i=10;i<=NF;i++)n=n "|" $i
        printf "%s{\"pane_id\":\"%s\",\"session\":\"%s\",\"window_index\":%d,\"pane_index\":%d,\"active\":%s,\"command\":\"%s\",\"cwd\":\"%s\",\"window\":\"%s\"}", (NR>1?",":""),e($1),e($2),$3,$4,(($5==1&&$6==1)?"true":"false"),e($7),e($8),e(n)}
        END{print "]"}'
    fi
    return 0
  fi
  { printf 'PANE|SESSION:WIN.PANE|WINDOW|COMMAND|CWD|ACT\n'
    printf '%s\n' "$rows" | awk -F'|' '{n=$9;for(i=10;i<=NF;i++)n=n "|" $i
      printf "%s|%s:%s.%s|%s|%s|%s|%s\n", $1,$2,$3,$4,n,$7,$8,(($5==1&&$6==1)?"*":"-")}'
  } | column -t -s '|'
}

cmd_new() {
  [ $# -ge 2 ] || usage
  local name=$1 command=$2 cwd=$PWD sess="" dup=0 sid
  shift 2
  while [ $# -gt 0 ]; do
    case $1 in
      --cwd) [ $# -ge 2 ] || usage; cwd=$2; shift ;;
      --session) [ $# -ge 2 ] || usage; sess=$2; shift ;;
      --allow-duplicate) dup=1 ;;
      *) die "opcao desconhecida: $1" ;;
    esac; shift
  done
  [ -n "$name" ] || die "nome vazio"
  [ -d "$cwd" ] || die "diretorio nao existe: $cwd"
  # sessao por igualdade exata, e o $id dela nos -t seguintes
  local sessions; sessions=$(tm list-sessions -F '#{session_id}|#{session_name}' 2>&1) || die "tmux sem servidor ou com erro: $sessions"
  if [ -z "$sess" ]; then
    if [ -n "${TMUX_PANE:-}" ]; then sess=$(tm display-message -p -t "$TMUX_PANE" '#{session_name}' 2>/dev/null || true); fi
    [ -n "$sess" ] || sess=$(printf '%s\n' "$sessions" | head -1 | cut -d'|' -f2-)
  fi
  sid=$(printf '%s\n' "$sessions" | awk -F'|' -v s="$sess" '{n=$2;for(i=3;i<=NF;i++)n=n "|" $i} n==s{print $1; exit}')
  [ -n "$sid" ] || die "sessao \"$sess\" nao existe. Sessoes: $(printf '%s' "$sessions" | cut -d'|' -f2- | tr '\n' ' ')"
  if [ "$dup" = 0 ]; then
    local clash
    clash=$(tm list-windows -t "$sid" -F '#{window_id}|#{window_index}|#{window_name}' | awk -F'|' -v n="$name" '{w=$3;for(i=4;i<=NF;i++)w=w "|" $i} w==n{print "  " $1 " (indice " $2 ")"}')
    [ -z "$clash" ] || die "ja existe janela \"$name\" na sessao $sess (use --allow-duplicate):
$clash"
  fi
  tm new-window -d -P -F '#{pane_id}' -t "${sid}:" -n "$name" -c "$cwd" "$command" || die "new-window falhou"
}

cmd_rename() {
  [ $# -eq 2 ] || usage
  local id; id=$(resolve_pane "$1") || exit $?
  [ -n "$2" ] || die "novo nome vazio"
  tm rename-window -t "$id" "$2" || die "rename-window falhou"
  printf 'janela de %s agora se chama "%s"\n' "$id" "$2"
}

[ $# -ge 1 ] || usage
sub=$1; shift
case $sub in
  list) cmd_list "$@" ;;
  new) cmd_new "$@" ;;
  rename) cmd_rename "$@" ;;
  *) usage ;;
esac
