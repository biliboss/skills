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
: "${DEVIN_BATCH_MAX:=3}"
# Caminho relativo vira absoluto uma vez; os filhos herdam o valor já absoluto.
case "$DEVIN_RUNS_DIR" in
  /*) ;;
  *) mkdir -p -- "$DEVIN_RUNS_DIR" && DEVIN_RUNS_DIR=$(CDPATH= cd -- "$DEVIN_RUNS_DIR" && pwd) || { echo "devin: DEVIN_RUNS_DIR inválido" >&2; exit 1; } ;;
esac
export DEVIN_RUNS_DIR
# Janela, em segundos, em que uma rodada sem pid ainda é considerada em largada.
START_GRACE=60

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

# ident_of <pid>: marca de identidade do processo (hora de início); vazio se não existe.
ident_of() {
  ps -o lstart= -p "$1" 2>/dev/null | tr -s ' ' | sed 's/^ //;s/ $//'
}

# group_alive <pgid>: há algum processo vivo no grupo? O número de um líder morto não é reaproveitado
# como pid enquanto o grupo tiver membros, então grupo vivo com esse número é o do worker (e do Devin órfão).
group_alive() {
  ps -axo pgid=,pid= 2>/dev/null | awk -v g="$1" '$1 == g { f = 1 } END { exit !f }'
}

# alive_of <pasta>: o worker (pid e hora de início conferidos) ou o grupo dele ainda vive.
alive_of() {
  [ -f "$1/pid" ] || return 1
  wpid=$(sed -n 1p "$1/pid")
  wident=$(sed -n 2p "$1/pid")
  case "$wpid" in ""|*[!0-9]*) return 1 ;; esac
  if [ -n "$wident" ] && [ "$(ident_of "$wpid")" = "$wident" ]; then return 0; fi
  group_alive "$wpid"
}

# state_of <pasta>: starting, running, done, failed ou lost.
# running: o worker ou o Devin (mesmo órfão) vive. starting: largada em curso, sem pid, por até START_GRACE s.
# lost: nada vivo e nenhuma saída gravada.
state_of() {
  if [ -f "$1/exit" ]; then
    if [ "$(cat "$1/exit" 2>/dev/null)" = 0 ]; then echo done; else echo failed; fi
  elif alive_of "$1"; then
    echo running
  elif [ -f "$1/exit" ]; then
    state_of "$1"
  elif [ ! -f "$1/pid" ] && [ -f "$1/starting" ]; then
    t=$(cat "$1/starting" 2>/dev/null || true)
    case "$t" in ""|*[!0-9]*) t=0 ;; esac
    if [ $(( $(date +%s) - t )) -lt "$START_GRACE" ]; then echo starting; else echo lost; fi
  else
    echo lost
  fi
}
