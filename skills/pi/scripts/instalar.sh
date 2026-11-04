#!/bin/sh
# instalar.sh: deixa o pi do Mac pronto para as contas do Claude.
#   Confere o pi, instala o pi-claude-bridge (versão fixa) se faltar e lista os modelos do provedor claude-bridge.
#   Para atualizar o catálogo de modelos: pi update.
set -eu
BRIDGE="${PI_CLAUDE_BRIDGE:-npm:pi-claude-bridge@0.9.3}"

command -v pi >/dev/null 2>&1 || { echo "instalar: pi não está no PATH (no Mac: brew install pi, ou o instalador do pi.dev)" >&2; exit 1; }
echo "pi $(pi --version 2>/dev/null)"

if pi list 2>/dev/null | grep -q 'pi-claude-bridge'; then
  echo "pi-claude-bridge já instalado"
else
  echo "instalando $BRIDGE (leia o código antes de trocar de versão)"
  pi install "$BRIDGE"
fi

echo "modelos do claude-bridge:"
pi --list-models claude-bridge 2>/dev/null | tail -n +2 | awk '{print "   " $2 "  ctx=" $3}'
