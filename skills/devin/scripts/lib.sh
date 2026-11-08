# lib.sh: configuração e funções comuns. Os outros scripts carregam com `. lib.sh`.
# --help imprime o comentário do topo do script que chamou.
case "${1:-}" in
  -h|--help) sed -n '2,/^[^#]/{/^#/s/^# *//p;}' "$0"; exit 0 ;;
esac
SKILL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="${DEVIN_SKILL_ENV:-$SKILL_DIR/.env}"
if [ -f "$ENV_FILE" ]; then
  . "$ENV_FILE"
fi
: "${DEVIN_BIN:=devin}"
: "${DEVIN_RUNS_DIR:=$HOME/.local/share/devin-runs}"
: "${DEVIN_SKILL_MODEL:=swe-2-max}"
: "${DEVIN_SKILL_MODE:=accept-edits}"

die() {
  echo "devin: $1" >&2
  exit "${2:-1}"
}

# run_dir <id>: imprime a pasta da rodada; recusa id vazio ou que saia de DEVIN_RUNS_DIR.
run_dir() {
  case "$1" in
    ""|*/*|.*) die "id inválido: '$1'" 2 ;;
  esac
  [ -d "$DEVIN_RUNS_DIR/$1" ] || die "rodada não encontrada: $1" 2
  printf '%s\n' "$DEVIN_RUNS_DIR/$1"
}

# state_of <pasta>: running, done, failed ou lost (o processo sumiu sem gravar a saída).
state_of() {
  if [ -f "$1/exit" ]; then
    if [ "$(cat "$1/exit")" = 0 ]; then echo done; else echo failed; fi
  elif [ -f "$1/pid" ] && kill -0 "$(cat "$1/pid")" 2>/dev/null; then
    echo running
  else
    echo lost
  fi
}
