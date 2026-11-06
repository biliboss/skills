#!/usr/bin/env bash
# lib.sh (sourced): binario do tmux, socket privado, die e o resolvedor de alvos.
# Nunca chama `tmux` sem caminho: no shell do dono `tmux` e um alias para new-session -A -s main.

die() { printf 'tmux-skill: %s\n' "$*" >&2; exit "${DIE_CODE:-1}"; }

_find_tmux() {
  if [ -n "${TMUX_BIN:-}" ]; then
    [ -x "$TMUX_BIN" ] && { printf '%s' "$TMUX_BIN"; return 0; }
    return 1
  fi
  if [ -x /opt/homebrew/bin/tmux ]; then printf '%s' /opt/homebrew/bin/tmux; return 0; fi
  command -v tmux 2>/dev/null
}
TMUX_BIN="$(_find_tmux)" || die "binario do tmux nao encontrado (defina TMUX_BIN)"

# tm <args>: o tmux, com -L <TMUX_SOCKET> quando definido (servidor privado de teste).
tm() {
  if [ -n "${TMUX_SOCKET:-}" ]; then "$TMUX_BIN" -L "$TMUX_SOCKET" "$@"; else "$TMUX_BIN" "$@"; fi
}

# id|session|window_index|pane_index|pane_active|window_active|command|cwd|window_name (nome por ultimo)
PANE_FMT='#{pane_id}|#{session_name}|#{window_index}|#{pane_index}|#{pane_active}|#{window_active}|#{pane_current_command}|#{pane_current_path}|#{window_name}'

# Imprime as linhas de PANE_FMT (stdin) como candidatos legiveis, em stderr.
_print_candidates() {
  awk -F'|' '{ n=$9; for(i=10;i<=NF;i++) n=n "|" $i
    printf "  %-6s %s:%s.%s  name=%s  cmd=%s\n", $1, $2, $3, $4, n, $7 }' | head -40 >&2
}

# Conta janelas distintas (sessao+indice) nas linhas de stdin.
_count_windows() { awk -F'|' '{print $2 "\034" $3}' | sort -u | wc -l | tr -d ' '; }

# resolve_pane <target> -> imprime o %id. Igualdade EXATA (nunca prefixo).
resolve_pane() {
  local target=$1 rows sel sess rest w p
  [ -n "$target" ] || die "alvo vazio"
  # T00..T99: o id do pane desta casa (opcao @tnn do pane, ver wiki panes-ids), por igualdade exata. O %N do tmux some
  # quando o pane fecha; o TNN fica. Sem achar, cai na regra do nome (uma janela pode se chamar T02 de verdade).
  if [[ $target =~ ^T[0-9][0-9]$ ]]; then
    sel=$(tm list-panes -a -F '#{pane_id}|#{@tnn}' 2>/dev/null | awk -F'|' -v t="$target" '$2==t {print $1}')
    case $(printf '%s' "$sel" | grep -c .) in
      1) printf '%s\n' "$sel"; return 0 ;;
      0) ;;
      *) printf 'tmux-skill: o id %s esta em varios panes (%s). Use o %%id.\n' "$target" "$(printf '%s' "$sel" | tr '\n' ' ')" >&2; exit 1 ;;
    esac
  fi
  rows=$(tm list-panes -a -F "$PANE_FMT" 2>&1) || die "tmux sem servidor ou com erro: $rows"
  # $1 = condicao awk; valores entram por ENVIRON (sem interpretar barras invertidas)
  _sel() {
    printf '%s\n' "$rows" | awk -F'|' "
      function nm(  n,i){ n=\$9; for(i=10;i<=NF;i++) n=n \"|\" \$i; return n }
      $1"
  }
  case $target in
    %*) sel=$(T=$target _sel '$1==ENVIRON["T"]') ;;
    *:*)
      sess=${target%%:*}; rest=${target#*:}
      sel=$(S=$sess W=$rest _sel '$2==ENVIRON["S"] && ($3==ENVIRON["W"] || nm()==ENVIRON["W"])')
      if [ -z "$sel" ] && [ "${rest#*.}" != "$rest" ]; then
        w=${rest%.*}; p=${rest##*.}
        sel=$(S=$sess W=$w P=$p _sel '$2==ENVIRON["S"] && ($3==ENVIRON["W"] || nm()==ENVIRON["W"]) && $4==ENVIRON["P"]')
      fi ;;
    *) sel=$(T=$target _sel 'nm()==ENVIRON["T"]') ;;
  esac
  if [ -z "$sel" ]; then
    printf 'tmux-skill: nenhum pane para o alvo "%s". Candidatos:\n' "$target" >&2
    printf '%s\n' "$rows" | _print_candidates
    exit 1
  fi
  if [ "$(printf '%s\n' "$sel" | _count_windows)" -gt 1 ]; then
    printf 'tmux-skill: alvo ambiguo "%s" (varias janelas). Use o %%id ou sessao:janela. Candidatos:\n' "$target" >&2
    printf '%s\n' "$sel" | _print_candidates
    exit 1
  fi
  if [ "$(printf '%s\n' "$sel" | wc -l | tr -d ' ')" -gt 1 ]; then
    # uma janela, varios panes e o alvo nao nomeou o pane: o ativo
    sel=$(printf '%s\n' "$sel" | awk -F'|' '$5==1' | head -1)
    [ -n "$sel" ] || die "janela sem pane ativo para \"$target\""
  fi
  printf '%s\n' "$sel" | head -1 | cut -d'|' -f1
}

# Tempo em ms (perl vem com o macOS; sem ele, segundos inteiros).
now_ms() { perl -MTime::HiRes=time -e 'printf "%d", time*1000' 2>/dev/null || printf '%s000' "$(date +%s)"; }

# s2ms <segundos, aceita decimal> -> ms inteiro; erro se nao for numero.
s2ms() {
  case $1 in ''|*[!0-9.]*|.*|*.|*.*.*) die "numero invalido: \"$1\"" ;; esac
  awk -v s="$1" 'BEGIN{printf "%d", s*1000}'
}

strip_ansi() { sed -E $'s/\x1b\\[[0-9;?]*[A-Za-z]//g'; }

# cap <pane id> [linhas de scrollback]: o conteudo do pane, linhas emendadas (-J), sem ANSI.
cap() { tm capture-pane -p -J -t "$1" -S "-${2:-2000}" | strip_ansi; }
