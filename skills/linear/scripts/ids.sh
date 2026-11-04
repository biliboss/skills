#!/bin/sh
# ids.sh: os ids fixos do Linear da casa (time, dono, app, estados, status de projeto), lidos do casa.env.
#   Use com: . "$(dirname "$0")/ids.sh"   (deixa as variáveis CASA_LINEAR_* no ambiente)
#   Rodado direto, imprime as chaves e os valores.
#   status de projeto (type): Ideia (backlog), Decidir (planned), Clone construindo / Espera uma pessoa / No ar, medindo (started), Resultado visto (completed)
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "ids: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; return 1 2>/dev/null || exit 1; }
. "$CASA"
: "${CASA_LINEAR_WORKSPACE:?ids: falta CASA_LINEAR_WORKSPACE em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_TIME_CHAVE:?ids: falta CASA_LINEAR_TIME_CHAVE em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_TIME_ID:?ids: falta CASA_LINEAR_TIME_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_DONO_ID:?ids: falta CASA_LINEAR_DONO_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_APP_BILI_ID:?ids: falta CASA_LINEAR_APP_BILI_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_ESTADO_TODO_ID:?ids: falta CASA_LINEAR_ESTADO_TODO_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_ESTADO_DOING_ID:?ids: falta CASA_LINEAR_ESTADO_DOING_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_ESTADO_DONE_ID:?ids: falta CASA_LINEAR_ESTADO_DONE_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_DOC_AGENTS_ID:?ids: falta CASA_LINEAR_DOC_AGENTS_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_STATUS_IDEIA_ID:?ids: falta CASA_LINEAR_STATUS_IDEIA_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_STATUS_DECIDIR_ID:?ids: falta CASA_LINEAR_STATUS_DECIDIR_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_STATUS_CONSTRUINDO_ID:?ids: falta CASA_LINEAR_STATUS_CONSTRUINDO_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_STATUS_ESPERA_PESSOA_ID:?ids: falta CASA_LINEAR_STATUS_ESPERA_PESSOA_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_STATUS_NO_AR_ID:?ids: falta CASA_LINEAR_STATUS_NO_AR_ID em $CASA (veja o casa.env.example)}"
: "${CASA_LINEAR_STATUS_RESULTADO_VISTO_ID:?ids: falta CASA_LINEAR_STATUS_RESULTADO_VISTO_ID em $CASA (veja o casa.env.example)}"
case "$0" in
  *ids.sh) for k in $(sed -n 's/^\([A-Z_]*\)=.*/\1/p' "$CASA" | grep '^CASA_LINEAR_'); do eval "printf '%s=%s\n' $k \"\$$k\""; done ;;
esac
