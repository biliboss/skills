# /// script
# requires-python = ">=3.11"
# dependencies = ["rich>=13"]
# ///
"""cartao.py: o cartão de um item da mesa do herdr, minimalista e colorido, com o rich.

Cada item em foco é uma aba: o cartão à esquerda (pane "card"), o agente à direita (e o worker, se houver).
O texto vem de ~/.local/state/<tema>.cartao.md, escrito pela sessão do item no estilo do .wiki/escrever-bem.md:

    # Título: o resultado visível, até ~55 caracteres
    ## Pronto
    Você abre X e vê Y.
    ## Feito
    - um item por linha
    ## Você confere
    - o link, a decisão

Sem ele, mostra o objetivo do briefing (~/.local/state/<tema>.md) e a última fala do agente. Só lê.

O pane do cartão mostra só o resumo. O nome e o estado de cada agente da aba vão no rótulo do pane dele, na barra
do herdr ("H14 - duplo-eval-tasks · parado · pi"), que o cartão mantém a cada volta. O Hermes (o Bili) o herdr não
reconhece como agente: o cartão o trata como "hermes" pelo título do terminal ou pelo id em MESA_BILI (H01).

    uv run cartao.py [segundos]        o cartão da aba onde o pane mora (HERDR_PANE_ID); redesenha a cada N s,
                                       num resize (SIGWINCH) e quando a largura do pane muda
    uv run cartao.py --uma             desenha uma vez e sai
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.text import Text

ESTADO = Path.home() / ".local/state"
ESTADO_NOME = {"working": "trabalhando", "blocked": "perguntando", "done": "terminou", "idle": "parado"}
BILI = os.environ.get("MESA_BILI", "H01")
HERMES = re.compile(r"\b(Bili|Hermes)\b")
RUIDO = re.compile(
    r"[─━═]{6,}|░▒▓|INSERT|MCP:|subagents|bypass permissions|ctrl\+o|^Took |^❯|^\$ |^goal_complete"
    r"|Working|Thinking|recap:|\(timeout|^[│┊]"
)


def herdr(*args: str) -> dict:
    out = subprocess.run(["herdr", *args], capture_output=True, text=True).stdout
    try:
        return json.loads(out).get("result", {})
    except json.JSONDecodeError:
        return {}


def ultima_fala(pane: str) -> str:
    """Os dois últimos parágrafos do pane do agente, sem moldura, barra de status nem comandos."""
    txt = subprocess.run(
        ["herdr", "pane", "read", pane, "--source", "recent-unwrapped", "--lines", "120"],
        capture_output=True, text=True,
    ).stdout
    blocos, atual = [], []
    for linha in txt.splitlines():
        linha = linha.strip()
        if not linha:
            if atual:
                blocos.append(" ".join(atual))
                atual = []
            continue
        if not RUIDO.search(linha):
            atual.append(linha)
    if atual:
        blocos.append(" ".join(atual))
    fala = "\n\n".join(blocos[-2:])
    return fala[:700] + " …" if len(fala) > 700 else fala


def secoes(md: str) -> list:
    """Título em negrito, rótulos apagados, o corpo de cada seção em markdown."""
    partes, corpo = [], []

    def fecha():
        if "".join(corpo).strip():
            partes.append(Markdown("\n".join(corpo), hyperlinks=False))
        corpo.clear()

    for linha in md.splitlines():
        if linha.startswith("# "):
            fecha()
            partes += [Text(""), Text(linha[2:].strip(), style="bold bright_white")]
        elif linha.startswith("## "):
            fecha()
            partes += [Text(""), Text(linha[3:].strip().upper(), style="grey50")]
        else:
            corpo.append(linha)
    fecha()
    return partes


def base(rotulo: str) -> str:
    """O rótulo sem o estado que o cartão acrescenta (\"H14 - tema · parado · pi\" -> \"H14 - tema\")."""
    return rotulo.split(" · ")[0]


def agente_de(p: dict) -> tuple[str, str]:
    """(agente, estado) do pane. O Hermes não é reconhecido pelo herdr: vem do título (⏳ = trabalhando) ou do id."""
    if p.get("agent"):
        return p["agent"], ESTADO_NOME.get(p.get("agent_status"), "?")
    titulo = p.get("terminal_title_stripped") or ""
    if HERMES.search(titulo) or base(p.get("label") or "").startswith(f"{BILI} - "):
        return "hermes", "trabalhando" if "⏳" in titulo else "parado"
    return "", ""


def da_aba(eu: str) -> tuple[str, list]:
    panes = herdr("pane", "list").get("panes", [])
    tab = next((p["tab_id"] for p in panes if p["pane_id"] == eu), None)
    tabs = herdr("tab", "list").get("tabs", [])
    tema = next((t["label"] for t in tabs if t["tab_id"] == tab), "?")
    return tema, [p for p in panes if p["tab_id"] == tab and p["pane_id"] != eu and p.get("label") != "card"]


def rotula(outros: list) -> None:
    """Põe o estado de cada agente no rótulo do pane dele (a barra do herdr), só quando muda."""
    for p in outros:
        agente, estado = agente_de(p)
        atual = p.get("label") or ""
        if not agente or not atual:
            continue
        novo = f"{base(atual)} · {estado} · {agente}"
        if novo != atual:
            subprocess.run(["herdr", "pane", "rename", p["pane_id"], novo], capture_output=True)


def cartao(tema: str, outros: list) -> Group:
    """Só o resumo: o cartão escrito pela sessão do item, ou o objetivo do briefing e a última fala."""
    escrito = ESTADO / f"{tema}.cartao.md"
    if escrito.exists():
        partes = secoes(escrito.read_text())
        return Group(*(partes[1:] if partes and not str(partes[0]) else partes))

    partes: list = []
    briefing = ESTADO / f"{tema}.md"
    if briefing.exists():
        b = briefing.read_text()
        m = re.search(r"^## Objetivo[^\n]*\n(.*?)(?=^## |\Z)", b, re.S | re.M)
        obj = (m.group(1) if m else b.splitlines()[0].lstrip("# ")).strip()
        partes += [Text(tema, style="bold bright_white"), Text(""), Text("OBJETIVO", style="grey50"), Markdown(obj)]
    for p in outros:
        if agente_de(p)[0] and not base(p.get("label") or "").startswith(f"{BILI} - "):
            fala = ultima_fala(p["pane_id"])
            if fala:
                partes += [Text(""), Text(f"ÚLTIMA FALA · {base(p.get('label') or 'agente')}", style="grey50"), Text(fala)]
    return Group(*partes)


def largura(eu: str) -> int:
    """A largura vem do herdr (o rect do próprio pane): dentro do pane o tamanho do tty engana."""
    for p in herdr("pane", "layout", "--pane", eu).get("layout", {}).get("panes", []):
        if p.get("pane_id") == eu:
            return max(20, int(p["rect"]["width"]) - 4)
    return 80


def desenha(eu: str, w: int | None = None) -> None:
    w = w or largura(eu)
    tema, outros = da_aba(eu)
    rotula(outros)
    con = Console(width=w, force_terminal=True, color_system="256")
    with con.capture() as cap:
        con.print(Padding(cartao(tema, outros), (0, 2, 0, 2)))
    sys.stdout.write("\033[H\033[2J\033[3J" + cap.get())
    sys.stdout.flush()


def main() -> None:
    eu = os.environ.get("HERDR_PANE_ID", "")
    if "--uma" in sys.argv:
        desenha(eu)
        return
    n = next((int(a) for a in sys.argv[1:] if a.isdigit()), 15)
    redesenhar = True
    signal.signal(signal.SIGWINCH, lambda *_: globals().__setitem__("_WINCH", True))
    w_antes, proxima = 0, 0.0
    while True:
        w = largura(eu)
        if redesenhar or globals().pop("_WINCH", False) or w != w_antes or time.monotonic() >= proxima:
            desenha(eu, w)
            w_antes, proxima, redesenhar = w, time.monotonic() + n, False
        time.sleep(1)


if __name__ == "__main__":
    main()
