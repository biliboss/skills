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
: "${DEVIN_SKILL_MODEL:=swe-2-medium}"
: "${DEVIN_MAX_PARALLEL:=8}"
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

# max_parallel: imprime o teto de rodadas simultâneas (DEVIN_MAX_PARALLEL, no máximo 8); recusa valor não numérico ou menor que 1.
max_parallel() {
  if ! printf '%s' "$DEVIN_MAX_PARALLEL" | grep -qE '^[0-9]+$'; then die "DEVIN_MAX_PARALLEL deve ser um inteiro >= 1: '$DEVIN_MAX_PARALLEL'" 2; fi
  if [ "$DEVIN_MAX_PARALLEL" -lt 1 ]; then die "DEVIN_MAX_PARALLEL deve ser >= 1: '$DEVIN_MAX_PARALLEL'" 2; fi
  if [ "$DEVIN_MAX_PARALLEL" -gt 8 ]; then echo 8; else echo "$DEVIN_MAX_PARALLEL"; fi
}

# running_count: quantas rodadas estão running em DEVIN_RUNS_DIR (todas, não só as de um lote).
running_count() {
  n=0
  for d in "$DEVIN_RUNS_DIR"/*/; do
    if [ -f "${d}meta.env" ] && [ "$(state_of "${d%/}")" = running ]; then n=$((n + 1)); fi
  done
  echo "$n"
}

# changed_files <worktree> <base>: arquivos alterados contra a base (commits, staged, unstaged e não rastreados não ignorados), um por linha.
changed_files() {
  { git -C "$1" -c core.quotepath=off diff --name-only --no-renames "$2"; git -C "$1" -c core.quotepath=off ls-files --others --exclude-standard; } | sort -u
}

# scope_violations <arquivo allowed>: lê caminhos no stdin e imprime os que não casam com nenhuma entrada.
# Entrada é caminho exato ou glob simples: * (sem /), ** (com /) e ?.
scope_violations() {
  awk '
    function rx(g,  i, c, r, n) {
      r = "^"; n = length(g)
      for (i = 1; i <= n; i++) {
        c = substr(g, i, 1)
        if (c == "*") { if (substr(g, i + 1, 1) == "*") { r = r ".*"; i++ } else r = r "[^/]*" }
        else if (c == "?") r = r "[^/]"
        else if (index(".+()[]{}|^$\\", c)) r = r "\\" c
        else r = r c
      }
      return r "$"
    }
    FNR == NR { if ($0 != "") pats[++np] = rx($0); next }
    { ok = 0; for (i = 1; i <= np; i++) if ($0 ~ pats[i]) { ok = 1; break } if (!ok) print }
  ' "$1" -
}
