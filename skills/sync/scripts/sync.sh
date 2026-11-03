#!/bin/sh
# Mantém os repos iguais ao remoto e sem sujeira, à mão.
#   sync.sh estado <repo>...                       ramo, à frente/atrás do origin e o que está sujo (faz fetch)
#   sync.sh enviar <repo> <arquivo-msg> <caminho>... rebase, lint do .wiki (se tocado), commit SÓ dos caminhos, push
# Nunca usa `git add -A`; nunca força push. Sai com 1 se algo impedir (lint vermelho, conflito, push recusado).
set -u
modo=${1:-}; shift 2>/dev/null || true

estado() {
  r=$1
  git -C "$r" fetch -q 2>/dev/null || echo "  (fetch falhou: sem rede ou sem acesso)"
  ramo=$(git -C "$r" rev-parse --abbrev-ref HEAD)
  ab=$(git -C "$r" rev-list --left-right --count "HEAD...@{u}" 2>/dev/null || echo "? ?")
  set -- $ab
  echo "$r · $ramo · à frente $1 · atrás $2"
  git -C "$r" status --porcelain=v1 | sed 's/^/  /'
}

lint_wiki() {
  r=$1; shift
  # só quando algum caminho do commit está no .wiki
  if printf '%s\n' "$@" | grep -q '^\.wiki/' && [ -d "$r/.wiki" ]; then
    # o wiki-smith vem no mesmo plugin: ../../wiki-smith/scripts a partir deste script
    L=$(cd "$(dirname "$0")/../../wiki-smith/scripts" 2>/dev/null && pwd)
    if [ -d "$L" ]; then
      (cd "$r" && "$L/dates.sh" -w .wiki >/dev/null && "$L/day-index.sh" -w .wiki >/dev/null)
      python3 -I "$L/lint.py" -w "$r/.wiki" || { echo "lint do .wiki vermelho: corrija antes do commit"; return 1; }
    fi
  fi
}

case "$modo" in
  estado)
    [ $# -gt 0 ] || set -- .
    for r in "$@"; do estado "$r"; done ;;
  enviar)
    [ $# -ge 3 ] || { echo "uso: sync.sh enviar <repo> <arquivo-msg> <caminho>..." >&2; exit 2; }
    r=$1; msg=$2; shift 2
    lint_wiki "$r" "$@" || exit 1
    git -C "$r" add -- "$@" || exit 1
    if git -C "$r" diff --cached --quiet; then echo "$r: nada a commitar nesses caminhos"; else
      git -C "$r" commit -q -F "$msg" || exit 1
    fi
    git -C "$r" pull -q --rebase --autostash || { echo "$r: rebase com conflito; resolva e rode de novo"; exit 1; }
    saida=$(git -C "$r" push -q origin HEAD 2>&1) || { echo "$r: push recusado:"; echo "$saida"; exit 1; }
    printf '%s\n' "$saida" | grep -q -i 'bypassed' && echo "$r: o push contornou a proteção do ramo (avise o Gabriel)"
    estado "$r" ;;
  *) echo "uso: sync.sh estado <repo>... | enviar <repo> <arquivo-msg> <caminho>..." >&2; exit 2 ;;
esac
