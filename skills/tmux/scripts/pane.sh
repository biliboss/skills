#!/usr/bin/env bash
# pane.sh: ler, mandar texto, mandar teclas e esperar num pane do tmux.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/lib.sh"

usage() {
  cat >&2 <<'U'
uso:
  pane.sh read <alvo> [N=30] [--keep-blank]
  pane.sh send <alvo> <texto> [--no-enter] [--timeout S=5] [--no-verify]
       (texto que comeca com -: pane.sh send <alvo> -- "-x ..." ; ou --stdin e o texto no stdin)
  pane.sh key  <alvo> <Tecla>...
  pane.sh wait <alvo> (--text REGEX | --idle S) --timeout S
alvo: %12 | nome-da-janela | sessao:janela | sessao:janela.pane
U
  exit 2
}

cmd_read() {
  [ $# -ge 1 ] || usage
  local target=$1 n=30 keep=0 id; shift
  while [ $# -gt 0 ]; do
    case $1 in
      --keep-blank) keep=1 ;;
      *[!0-9]*|'') die "N invalido: \"$1\"" ;;
      *) n=$1 ;;
    esac; shift
  done
  id=$(resolve_pane "$target") || exit $?
  if [ "$keep" = 1 ]; then
    cap "$id" 5000 | sed -E 's/[[:space:]]+$//' | tail -n "$n"
  else
    cap "$id" 5000 | sed -E 's/[[:space:]]+$//' | { grep -v '^$' || true; } | tail -n "$n"
  fi
}

cmd_key() {
  [ $# -ge 2 ] || usage
  local id; id=$(resolve_pane "$1") || exit $?; shift
  tm send-keys -t "$id" "$@"
}

# ocorrencias de $2 (texto fixo) no pane $1
_count() { cap "$1" 2000 | { grep -cF -- "$2" || true; }; }
_count_marker() { cap "$1" 2000 | { grep -cE '\[Pasted text' || true; }; }

cmd_send() {
  [ $# -ge 2 ] || usage
  local target=$1 text enter=1 tmo=5 verify=1 id multi=0 tail_ line before bm
  if [ "$2" = "--stdin" ]; then text=$(cat); shift 2
  elif [ "$2" = "--" ]; then [ $# -ge 3 ] || usage; text=$3; shift 3
  else text=$2; shift 2; fi
  while [ $# -gt 0 ]; do
    case $1 in
      --no-enter) enter=0 ;;
      --no-verify) verify=0 ;;
      --timeout) [ $# -ge 2 ] || usage; tmo=$2; shift ;;
      *) die "opcao desconhecida: $1" ;;
    esac; shift
  done
  [ -n "$text" ] || die "texto vazio"
  local tmo_ms; tmo_ms=$(s2ms "$tmo")
  id=$(resolve_pane "$target") || exit $?
  case $text in *$'\n'*) multi=1 ;; esac

  # ultima linha nao vazia, sem ANSI, ultimos ~30 caracteres
  line=$(printf '%s\n' "$text" | strip_ansi | sed -E 's/[[:space:]]+$//' | awk 'NF{l=$0} END{print l}')
  tail_=$line
  [ "${#line}" -gt 30 ] && tail_=${line: -30}
  tail_=${tail_#"${tail_%%[![:space:]]*}"}
  before=0; bm=0
  if [ "$verify" = 1 ]; then before=$(_count "$id" "$tail_"); bm=$(_count_marker "$id"); fi

  if [ "$multi" = 1 ]; then
    local f buf; f=$(mktemp "${TMPDIR:-/tmp}/tmux-skill.XXXXXX") || die "mktemp falhou"
    buf="skill-tmux-$$-$RANDOM"
    printf '%s' "$text" > "$f"
    tm load-buffer -b "$buf" "$f" || die "load-buffer falhou ($f)"
    tm paste-buffer -p -d -b "$buf" -t "$id" || die "paste-buffer falhou"
    rm -f -- "$f"
  else
    tm send-keys -t "$id" -l -- "$text" || die "send-keys falhou"
  fi

  if [ "$verify" = 1 ]; then
    local deadline=$(( $(now_ms) + tmo_ms )) ok=0
    while :; do
      if [ "$(_count "$id" "$tail_")" -gt "$before" ]; then ok=1; break; fi
      if [ "$multi" = 1 ] && [ "$(_count_marker "$id")" -gt "$bm" ]; then ok=1; break; fi
      [ "$(now_ms)" -ge "$deadline" ] && break
      sleep 0.1
    done
    if [ "$ok" = 0 ]; then
      printf 'tmux-skill: o fim do texto ("%s") nao apareceu em %s em %ss; Enter NAO enviado. O pane pode ter texto parcial.\n' "$tail_" "$id" "$tmo" >&2
      exit 124
    fi
  fi
  if [ "$enter" = 1 ]; then tm send-keys -t "$id" Enter || die "Enter falhou"; fi
  printf 'enviado a %s\n' "$id"
}

cmd_wait() {
  [ $# -ge 1 ] || usage
  local target=$1 mode="" arg="" tmo="" id; shift
  while [ $# -gt 0 ]; do
    case $1 in
      --text) [ $# -ge 2 ] || usage; [ -z "$mode" ] || die "use so um entre --text e --idle"; mode=text; arg=$2; shift ;;
      --idle) [ $# -ge 2 ] || usage; [ -z "$mode" ] || die "use so um entre --text e --idle"; mode=idle; arg=$2; shift ;;
      --timeout) [ $# -ge 2 ] || usage; tmo=$2; shift ;;
      *) die "opcao desconhecida: $1" ;;
    esac; shift
  done
  [ -n "$mode" ] || die "falta --text ou --idle"
  [ -n "$tmo" ] || die "falta --timeout (nao ha espera sem prazo)"
  local tmo_ms deadline start; tmo_ms=$(s2ms "$tmo")
  id=$(resolve_pane "$target") || exit $?
  start=$(now_ms); deadline=$((start + tmo_ms))
  local snap hit sum last_sum="" last_change idle_ms=0
  [ "$mode" = idle ] && idle_ms=$(s2ms "$arg")
  last_change=$start
  while :; do
    snap=$(cap "$id" 200 | sed -E 's/[[:space:]]+$//' | { grep -v '^$' || true; })
    if [ "$mode" = text ]; then
      hit=$(printf '%s\n' "$snap" | grep -E -- "$arg" | tail -1)
      if [ -n "$hit" ]; then printf '%s\n' "$hit"; exit 0; fi
    else
      sum=$(printf '%s' "$snap" | cksum)
      if [ "$sum" != "$last_sum" ]; then last_sum=$sum; last_change=$(now_ms); fi
      if [ $(( $(now_ms) - last_change )) -ge "$idle_ms" ]; then printf '%s\n' "$snap" | tail -10; exit 0; fi
    fi
    if [ "$(now_ms)" -ge "$deadline" ]; then
      printf '%s\n' "$snap" | tail -10
      printf 'tmux-skill: prazo de %ss esgotado em %s (%s)\n' "$tmo" "$id" "$mode" >&2
      exit 124
    fi
    sleep 0.2
  done
}

[ $# -ge 1 ] || usage
sub=$1; shift
case $sub in
  read) cmd_read "$@" ;;
  send) cmd_send "$@" ;;
  key) cmd_key "$@" ;;
  wait) cmd_wait "$@" ;;
  *) usage ;;
esac
