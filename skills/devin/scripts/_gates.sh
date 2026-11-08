#!/bin/sh
# _gates.sh <diretório> [arquivo...]: uso interno de gate.sh e merge.sh. Roda os gates do .pre-commit-config.yaml
# do diretório com o prek, nos arquivos dados (sem precisar de commit): primeiro o estágio pre-commit, depois o pre-push.
# Sem arquivos, só confere se os gates podem rodar. Saída: 0 passou, 1 reprovou, 2 não pôde rodar (sem config ou sem prek).
set -u
. "$(dirname -- "$0")/lib.sh"

[ $# -ge 1 ] || die "uso: _gates.sh <diretório> [arquivo...]" 2
dir="$1"
shift
[ -d "$dir" ] || die "diretório não encontrado: $dir" 2
[ -f "$dir/.pre-commit-config.yaml" ] || die "sem .pre-commit-config.yaml em $dir: os gates não podem rodar (modelo em templates/gates)" 2
command -v prek >/dev/null 2>&1 || die "prek não instalado: os gates não podem rodar (brew install prek)" 2
[ $# -gt 0 ] || exit 0

status=0
for stage in pre-commit pre-push; do
  echo "== gates $stage"
  (cd "$dir" && prek run --stage "$stage" --color never --files "$@") || status=1
done
exit "$status"
