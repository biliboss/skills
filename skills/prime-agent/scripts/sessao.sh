#!/bin/sh
# sessao.sh <tema|pasta> [n]: a sessão mais nova do Prime Agent naquela pasta, resumida.
#   Mostra o id (para --resume), as últimas n células do REPL (padrão 15) com o tamanho do resultado,
#   os erros e os tokens de cada turno. Lê ~/.prime/agent/sessions/*.jsonl; só leitura.
# Não lê stdin.
set -eu
[ $# -ge 1 ] || { sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
LAB="${PRIME_LAB:-$HOME/src/prime-agent-lab}"
alvo=$1
[ -d "$alvo" ] || alvo="$LAB/$1"
[ -d "$alvo" ] || { echo "sessao: pasta não existe: $alvo" >&2; exit 1; }
alvo=$(cd "$alvo" && pwd)
exec python3 -I - "$HOME/.prime/agent/sessions" "$alvo" "${2:-15}" <<'PY'
import json, os, sys, glob
pasta, alvo, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
achou = None
for f in sorted(glob.glob(os.path.join(pasta, "*.jsonl")), key=os.path.getmtime, reverse=True):
    with open(f) as h:
        primeira = h.readline()
    try:
        if json.loads(primeira).get("cwd") == alvo:
            achou = f
            break
    except ValueError:
        continue
if not achou:
    sys.exit(f"sessao: nenhuma sessão do Prime Agent com cwd {alvo}")
linhas = [json.loads(l) for l in open(achou)]
print("id:", os.path.basename(achou)[:-6])
modelo = [r for r in linhas if r.get("type") == "model_change"]
if modelo:
    print("modelo:", modelo[-1].get("provider"), modelo[-1].get("modelId"))
eventos = []
for r in linhas:
    if r.get("type") != "message":
        continue
    m = r["message"]
    hora = r.get("timestamp", "")[11:19]
    if m["role"] == "assistant":
        u = m.get("usage", {})
        for b in m["content"]:
            if b.get("type") == "toolCall":
                codigo = json.dumps(b.get("arguments", {}).get("code", ""), ensure_ascii=False)[1:90]
                eventos.append(f"{hora} célula  in={u.get('input')} cache={u.get('cacheRead')}  {codigo}")
            elif b.get("type") == "text" and b["text"].strip():
                eventos.append(f"{hora} texto   {b['text'].strip()[:110]}")
    elif m["role"] == "toolResult":
        txt = "".join(x.get("text", "") for x in m["content"] if isinstance(x, dict))
        erro = " ERRO" if m.get("isError") or "Traceback" in txt else ""
        eventos.append(f"{hora} result  {len(txt)} chars{erro}")
print(f"células: {sum(1 for e in eventos if ' célula ' in e)}, erros: {sum(1 for e in eventos if e.endswith('ERRO'))}")
for e in eventos[-n:]:
    print(" ", e)
PY
