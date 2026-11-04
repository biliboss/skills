# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""barra.py: a barra de título do agente da frente no focus, e o vigia do focus.

Roda num pane de uma linha (rótulo "barra"), entre o resumo (o pane "card", em cima à esquerda) e o agente da frente
(embaixo à esquerda). O Bili (o pane MESA_BILI, padrão H01) fica à direita, de cima a baixo. A cada volta (2 s) ela:

- escreve numa linha o nome, o estado e o harness do agente da frente ("● H14 - duplo-eval-tasks · trabalhando · pi");
- devolve as proporções do focus quando o agente da frente troca ou some, ou quando saem do lugar: o resumo com 70% da
  altura da coluna da esquerda, a barra com 2 linhas, a coluna da esquerda com 45% da largura;
- avisa: quando o agente da frente para, troca ou some, põe na fila do Bili (mux.sh fila) para ele puxar o próximo;
  quando qualquer agente da mesa fica `blocked` (uma pergunta, uma aprovação), avisa o Gabriel na hora (notificação do
  macOS) e o Bili. Cada aviso sai uma vez por transição, e cada um vai também ao NATS (`mesa.focus.<evento>`).

    uv run barra.py            o vigia, em laço (no pane "barra")
    uv run barra.py --uma      desenha a barra uma vez e sai (teste)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

BILI = os.environ.get("MESA_BILI", "H01")
MUX = os.environ.get("MESA_MUX", os.path.expanduser("~/src/skills.wt-prime-mux/skills/prime-agent/scripts/mux.sh"))
HERMES = re.compile(r"\b(Bili|Hermes)\b")
NOME = {"working": "trabalhando", "blocked": "perguntando", "done": "terminou", "idle": "parado"}
COR = {"working": "32", "blocked": "1;33", "done": "36", "idle": "90"}
ICONE = {"working": "●", "blocked": "?", "done": "✓", "idle": "○"}
ALTURA_RESUMO, LARGURA_ESQ, ALTURA_BARRA = 0.70, 0.45, 2


def herdr(*args: str) -> dict:
    out = subprocess.run(["herdr", *args], capture_output=True, text=True).stdout
    try:
        return json.loads(out).get("result", {})
    except json.JSONDecodeError:
        return {}


def base(rotulo: str | None) -> str:
    return (rotulo or "").split(" · ")[0]


def eh_bili(p: dict) -> bool:
    """O pane do Bili: o id em MESA_BILI ou o Hermes no título do terminal (o id já mudou de nome)."""
    return base(p.get("label")).startswith(f"{BILI} - ") or bool(HERMES.search(p.get("terminal_title_stripped") or ""))


def estado(p: dict) -> tuple[str, str]:
    """(harness, agent_status). O herdr não reconhece o Hermes: vem do título (⏳ = trabalhando)."""
    if p.get("agent"):
        return p["agent"], p.get("agent_status") or "unknown"
    titulo = p.get("terminal_title_stripped") or ""
    if eh_bili(p):
        return "hermes", "working" if "⏳" in titulo else "idle"
    return "-", p.get("agent_status") or "unknown"


def avisa_bili(texto: str) -> None:
    alvo = BILI
    for p in herdr("pane", "list").get("panes", []):
        if eh_bili(p) and re.match(r"^H\d\d - ", p.get("label") or ""):
            alvo = p["label"][:3]
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(texto)
    subprocess.run(["sh", MUX, "fila", alvo, f.name], capture_output=True)
    os.unlink(f.name)


def avisa_gabriel(titulo: str, texto: str) -> None:
    script = f'display notification {json.dumps(texto)} with title {json.dumps(titulo)} sound name "Glass"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def nats(evento: str, dados: dict) -> None:
    if shutil.which("nats"):
        subprocess.run(["nats", "pub", f"mesa.focus.{evento}", json.dumps(dados, ensure_ascii=False)], capture_output=True)


def desenha(frente: dict | None, largura: int) -> None:
    if not frente:
        linha = "\033[90m· sem agente na frente: o Bili puxa o próximo\033[0m"
    else:
        harness, st = estado(frente)
        linha = (f"\033[{COR.get(st, '90')}m{ICONE.get(st, '·')} \033[1;97m{base(frente.get('label')) or '?'}"
                 f"\033[0;90m · {NOME.get(st, st)} · {harness}\033[0m")
    sys.stdout.write("\033[H\033[2J\033[3J" + linha[: largura + 40])
    sys.stdout.flush()


def rects(eu: str) -> dict:
    return {p["pane_id"]: p["rect"] for p in herdr("pane", "layout", "--pane", eu).get("layout", {}).get("panes", [])}


def proporcoes(card: str, eu: str, frente: str | None, r: dict) -> None:
    """Devolve as proporções: o resumo com 70% da coluna da esquerda, a barra com 2 linhas, a esquerda com 45%."""
    if card not in r or eu not in r:
        return
    total_w = max(x["x"] + x["width"] for x in r.values())
    total_h = max(x["y"] + x["height"] for x in r.values())
    d = round(LARGURA_ESQ * total_w) - r[card]["width"]
    if abs(d) > 2:
        herdr("pane", "resize", "--pane", card, "--direction", "right" if d > 0 else "left", "--amount", f"{abs(d) / total_w:.3f}")
    esq_h = r[card]["height"] + r[eu]["height"] + (r[frente]["height"] if frente in r else 0)
    d = round(ALTURA_RESUMO * esq_h) - r[card]["height"]
    if abs(d) > 1:
        herdr("pane", "resize", "--pane", card, "--direction", "down" if d > 0 else "up", "--amount", f"{abs(d) / total_h:.3f}")
    if frente:
        r = rects(eu)
        d = r.get(eu, {}).get("height", ALTURA_BARRA) - ALTURA_BARRA
        if d > 0:
            herdr("pane", "resize", "--pane", frente, "--direction", "up", "--amount", f"{d / total_h:.3f}")


def main() -> None:
    eu = os.environ.get("HERDR_PANE_ID", "")
    antes: dict = {}          # pane_id -> agent_status, de toda a mesa
    frente_antes, st_antes = "", ""
    while True:
        panes = herdr("pane", "list").get("panes", [])
        minha = next((p for p in panes if p["pane_id"] == eu), None)
        if not minha:
            time.sleep(2)
            continue
        aba = [p for p in panes if p["tab_id"] == minha["tab_id"]]
        card = next((p["pane_id"] for p in aba if p.get("label") == "card"), "")
        r = rects(eu)
        # o agente da frente: na coluna da barra, logo abaixo dela
        x0 = r.get(eu, {}).get("x", 0)
        abaixo = [p for p in aba if p["pane_id"] not in (eu, card) and not eh_bili(p) and r.get(p["pane_id"], {}).get("x", -1) == x0]
        frente = min(abaixo, key=lambda p: r[p["pane_id"]]["y"], default=None)
        desenha(frente, r.get(eu, {}).get("width", 80))
        if "--uma" in sys.argv:
            return

        fid = frente["pane_id"] if frente else ""
        st = estado(frente)[1] if frente else ""
        nome = base(frente.get("label")) if frente else ""
        if fid != frente_antes:
            proporcoes(card, eu, fid or None, r)
            if frente_antes and not fid:
                avisa_bili(f"[focus] O agente da frente saiu do focus. Puxe o próximo item (fase.sh focar) e devolva o layout.")
                nats("sumiu", {"de": frente_antes})
        elif fid and st != st_antes and st in ("idle", "done") and st_antes == "working":
            avisa_bili(f"[focus] {nome} parou ({NOME[st]}). Confira o resultado, atualize o resumo e puxe o próximo se ele terminou.")
            nats("parou", {"pane": nome, "estado": st})

        # blocked em qualquer pane da mesa: o Gabriel na hora
        for p in panes:
            s = estado(p)[1]
            if s == "blocked" and antes.get(p["pane_id"]) not in (None, "blocked"):
                n = base(p.get("label")) or p["pane_id"]
                avisa_gabriel("Mesa: um agente pergunta", f"{n} está esperando você (pergunta ou aprovação).")
                avisa_bili(f"[focus] {n} ficou blocked (pergunta ou aprovação). O Gabriel foi avisado; traga-o ao focus se ele pedir.")
                nats("blocked", {"pane": n})
            antes[p["pane_id"]] = s
        frente_antes, st_antes = fid, st
        time.sleep(2)


if __name__ == "__main__":
    main()
