#!/bin/sh
# vps.sh: mostra como o pi da VPS chega aos provedores, sem imprimir credencial.
#   Para cada ~/.pi/agent da VPS: os provedores logados (só o tipo), o padrão e o anthropic pronto ou não.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "vps: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_VPS_HOST:?vps: falta CASA_VPS_HOST em $CASA (veja o casa.env.example)}"
ssh -o BatchMode=yes "$CASA_VPS_HOST" '
  sudo -n find /root /home -maxdepth 4 -path "*/.pi/agent" -type d 2>/dev/null | while read d; do
    echo "== $d"
    sudo -n jq -r "to_entries[]|\"   \"+.key+\": \"+(.value.type//\"?\")" "$d/auth.json" 2>/dev/null || echo "   sem auth.json"
    sudo -n jq -r "\"   padrão: \"+(.defaultProvider//\"-\")+\" / \"+(.defaultModel//\"-\")" "$d/settings.json" 2>/dev/null || true
  done
  echo "== pi do root: $(sudo -n /root/.local/share/pnpm/bin/pi --version 2>/dev/null || echo "?")"
  r=$(sudo -n -H /root/.local/share/pnpm/bin/pi auth check --provider anthropic --json --no-refresh 2>&1 || true)
  case "$r" in
    *"Unknown auth command"*) echo "   anthropic: este pi não tem \"auth check\" (chegou na 0.84); vale o tipo no auth.json acima" ;;
    *) echo "   anthropic: $r" ;;
  esac
'
