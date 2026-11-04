#!/bin/sh
# ligar-skills.sh: põe no pi as skills deste plugin (biliboss/skills),
#   como links em ~/.pi/agent/skills/<nome> para as pastas deste clone, lidas do .claude-plugin/plugin.json dele.
#   Uma skill que saiu do plugin.json tem o link movido para ~/.pi/agent/skills-desligadas/ (nada é apagado).
#   Rode depois de criar ou tirar uma skill do plugin; no pi aberto, mande /reload.
set -eu
repo=$(cd "$(dirname "$0")/../../.." && pwd)
DEST="$HOME/.pi/agent/skills"
FORA="$HOME/.pi/agent/skills-desligadas"
mkdir -p "$DEST" "$FORA"

if [ ! -f "$repo/.claude-plugin/plugin.json" ]; then
  echo "ligar: sem $repo/.claude-plugin/plugin.json" >&2
  exit 1
fi
ativas=""
for rel in $(jq -r '.skills[]' "$repo/.claude-plugin/plugin.json"); do
  pasta="$repo/${rel#./}"
  nome=$(basename "$pasta")
  ln -sfn "$pasta" "$DEST/$nome"
  ativas="$ativas $nome"
  echo "ligada: $nome"
done

# Links para este clone que não estão mais no plugin saem do caminho.
for l in "$DEST"/*; do
  [ -L "$l" ] || continue
  alvo=$(readlink "$l")
  case "$alvo" in
    "$repo/"*) ;;
    *) continue ;;
  esac
  nome=$(basename "$l")
  case " $ativas " in *" $nome "*) continue ;; esac
  mv "$l" "$FORA/$nome"
  echo "desligada: $nome"
done
