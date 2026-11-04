#!/bin/sh
# pi-claude.sh <conta> [args do pi...]: roda o pi com uma conta do Claude (pela assinatura), via pi-claude-bridge.
#   conta: o nome da conta principal ou da secundária, como no casa.env (cada uma aponta para um CLAUDE_CONFIG_DIR)
#   Sem --model nos args, usa $PI_CLAUDE_MODEL ou claude-bridge/claude-sonnet-5.
#   Exemplos:
#     pi-claude.sh <conta> -p "resuma o README"
#     pi-claude.sh <outra-conta> -p --model claude-bridge/claude-haiku-4-5 "Responda só: ok"
#     pi-claude.sh <conta>            # interativo
# Não lê stdin: o prompt vai como argumento.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "pi-claude: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_CONTA_PRINCIPAL_NOME:?pi-claude: falta CASA_CONTA_PRINCIPAL_NOME em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_PRINCIPAL_DIR:?pi-claude: falta CASA_CONTA_PRINCIPAL_DIR em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_SECUNDARIA_NOME:?pi-claude: falta CASA_CONTA_SECUNDARIA_NOME em $CASA (veja o casa.env.example)}"
: "${CASA_CONTA_SECUNDARIA_DIR:?pi-claude: falta CASA_CONTA_SECUNDARIA_DIR em $CASA (veja o casa.env.example)}"

uso() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || uso

case "$1" in
  "$CASA_CONTA_PRINCIPAL_NOME")   dir="$CASA_CONTA_PRINCIPAL_DIR" ;;
  "$CASA_CONTA_SECUNDARIA_NOME") dir="$CASA_CONTA_SECUNDARIA_DIR" ;;
  -h|--help) uso ;;
  *) echo "pi-claude: conta desconhecida '$1' (use $CASA_CONTA_PRINCIPAL_NOME ou $CASA_CONTA_SECUNDARIA_NOME)" >&2; exit 2 ;;
esac
shift

[ -d "$dir" ] || { echo "pi-claude: $dir não existe; faça o login com: CLAUDE_CONFIG_DIR=$dir claude auth login" >&2; exit 1; }
command -v pi >/dev/null 2>&1 || { echo "pi-claude: pi não está no PATH; rode scripts/instalar.sh" >&2; exit 1; }

tem_model=0
for a in "$@"; do
  case "$a" in --model|--model=*|--provider|--provider=*) tem_model=1 ;; esac
done

export CLAUDE_CONFIG_DIR="$dir"
if [ "$tem_model" = 1 ]; then
  exec pi "$@"
else
  exec pi --model "${PI_CLAUDE_MODEL:-claude-bridge/claude-sonnet-5}" "$@"
fi
