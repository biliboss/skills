#!/bin/sh
# configurar.sh [--instalar]: deixa o Prime Agent pronto e calado nesta máquina.
#   Confere o binário; com --instalar, baixa o instalador oficial para uma pasta temporária e pede que você o leia
#   antes (imprime o caminho e para). Depois põe o padrão zai / glm-5.3-flash e desliga traces e telemetria
#   em ~/.prime/agent/settings.json, mantendo o resto. Idempotente. Não lê stdin.
set -eu
BIN="${PRIME_AGENT_BIN:-$HOME/.local/bin/prime-agent}"
CONF="$HOME/.prime/agent/settings.json"
URL="https://app.primeintellect.ai/prime-agent/install.sh"
if [ ! -x "$BIN" ]; then
  if [ "${1:-}" = "--instalar" ]; then
    d=$(mktemp -d)
    curl -fsSL "$URL" -o "$d/install.sh"
    echo "configurar: o instalador está em $d/install.sh ($(wc -l < "$d/install.sh") linhas)."
    echo "Leia, e então rode: sh $d/install.sh </dev/null"
    exit 3
  fi
  echo "configurar: falta o $BIN; rode com --instalar" >&2
  exit 1
fi
echo "prime-agent $("$BIN" --version 2>/dev/null)"
mkdir -p "$(dirname "$CONF")"
python3 -I - "$CONF" <<'PY'
import json, os, sys
p = sys.argv[1]
d = json.load(open(p)) if os.path.exists(p) else {}
d.setdefault("telemetry", {})["enabled"] = False
d["agentTraces"] = {"enabled": False}
d["defaultProvider"], d["defaultModel"] = "zai", "glm-5.3-flash"
json.dump(d, open(p, "w"), indent=2)
print("settings: traces off, telemetria off, padrão zai/glm-5.3-flash")
PY
