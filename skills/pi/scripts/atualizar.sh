#!/bin/sh
# atualizar.sh [mac|vps|tudo]: põe todo pi na versão mais nova, com as extensões e os catálogos de modelos.
#   mac:  pi update --all (o pi e as extensões sem versão fixa) e pi update --models.
#   vps:  o pi do root (pnpm global) para @earendil-works/pi-coding-agent@latest, os catálogos dele,
#         e pi update --all em cada usuário de CASA_VPS_USUARIOS_PI. Não troca o pi se houver um rodando.
#   tudo: os dois (o padrão).
#   No fim, confere os logins OAuth do root na VPS (com renovação): "invalid" pede /login do dono.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] || { echo "atualizar: falta o arquivo $CASA; copie o casa.env.example (raiz do repo biliboss/skills) para lá e preencha" >&2; exit 1; }
. "$CASA"
: "${CASA_VPS_HOST:?atualizar: falta CASA_VPS_HOST em $CASA (veja o casa.env.example)}"
: "${CASA_VPS_USUARIOS_PI:?atualizar: falta CASA_VPS_USUARIOS_PI em $CASA (veja o casa.env.example)}"
alvo="${1:-tudo}"

mac() {
  echo "== Mac"
  pi update --all --no-approve 2>&1 | grep -E 'Updated|up to date|Installed' || true
  pi update --models --no-approve 2>&1 | tail -1
  echo "   pi $(pi --version)"
  pi list 2>/dev/null | grep -E '@[0-9]+\.[0-9]+' | sed 's/^/   fixado (não atualiza sozinho): /' || true
}

vps() {
  echo "== $CASA_VPS_HOST"
  ssh -o BatchMode=yes "$CASA_VPS_HOST" '
    if ps -eo args | grep -E "pi-coding-agent|/bin/pi( |$)" | grep -v grep >/dev/null; then
      echo "   há um pi rodando; não troco agora"; exit 0
    fi
    sudo -n -H sh -c "export PNPM_HOME=/root/.local/share/pnpm PATH=/root/.local/share/pnpm/bin:/root/.local/share/pnpm:\$PATH
      pnpm add -g @earendil-works/pi-coding-agent@latest >/dev/null 2>&1 || echo \"   pnpm falhou\"
      echo \"   root: pi \$(pi --version)\"
      pi update --models --no-approve >/dev/null 2>&1 || true
      for p in anthropic openai-codex zai; do echo \"   root \$p: \$(pi auth check --provider \$p --json 2>&1 | tr -d \"\\n\" | cut -c1-120)\"; done"
    for u in '"$CASA_VPS_USUARIOS_PI"'; do
      sudo -n -u $u -H sh -lc "cd ~ && pi update --all --no-approve >/dev/null 2>&1; echo \"   $u: pi \$(pi --version)\"" 2>/dev/null || true
    done
  '
}

case "$alvo" in
  mac) mac ;;
  vps) vps ;;
  tudo) mac; vps ;;
  *) echo "uso: atualizar.sh [mac|vps|tudo]" >&2; exit 2 ;;
esac
