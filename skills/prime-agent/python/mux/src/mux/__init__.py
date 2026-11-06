"""mux: tmux and herdr panes from the Prime Agent REPL, as thin wrappers over the duplo-local-agents skill's mux.sh.

mux.sh holds the logic (ids TNN/HNN, which multiplexer owns a pane); these functions only call it, so the
shell and the REPL behave the same.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

def _find_mux_sh() -> Path:
    """$MUX_SH, else the sibling duplo-local-agents skill (this file sits in prime-agent/python/mux/src/mux/), else the installed plugin, else
    the source clone. The kernel may run an installed copy of this package, far from the skill folder."""
    if os.environ.get("MUX_SH"):
        return Path(os.environ["MUX_SH"])
    here = Path(__file__).resolve()
    cands = [here.parents[4].parent / "duplo-local-agents" / "scripts" / "mux.sh"] if len(here.parents) > 4 else []
    home = Path.home()
    cands += sorted(home.glob(".claude*/plugins/cache/biliboss/biliboss-skills/*/skills/duplo-local-agents/scripts/mux.sh"), reverse=True)
    cands.append(home / "src/skills/skills/duplo-local-agents/scripts/mux.sh")
    for c in cands:
        if c.is_file():
            return c
    raise RuntimeError("mux: não achei o mux.sh da skill duplo-local-agents; defina MUX_SH")


MUX_SH = _find_mux_sh()


def _run(*args: str) -> str:
    r = subprocess.run(["sh", str(MUX_SH), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f"mux.sh {args[0]} saiu com {r.returncode}")
    return r.stdout


def qual() -> str:
    """Which multiplexer opens panes here: herdr, tmux or nenhum."""
    return _run("qual").strip()


def panes() -> list[dict[str, str]]:
    """Every pane of tmux and herdr: id (TNN/HNN or '-'), mux, pane (native id), nome, estado."""
    out = []
    for line in _run("panes").splitlines():
        parts = line.split("\t")
        if len(parts) == 5:
            out.append(dict(zip(("id", "mux", "pane", "nome", "estado"), parts)))
    return out


def ler(pane: str, linhas: int = 80) -> str:
    """The last lines of the pane's screen."""
    return _run("ler", pane, str(linhas))


def tecla(pane: str, tecla: str) -> None:
    """Send one key (Down, Enter, Escape, C-o)."""
    _run("tecla", pane, tecla)


def _envia(verbo: str, pane: str, texto: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(texto)
        path = f.name
    try:
        _run(verbo, pane, path)
    finally:
        os.unlink(path)


def manda(pane: str, texto: str) -> None:
    """Paste the text as one message and press Enter (steers the turn in progress: only to correct course)."""
    _envia("manda", pane, texto)


def fila(pane: str, texto: str) -> None:
    """Paste the text and queue it for the agent's next turn (Tab in Hermes): the default for anything not urgent."""
    _envia("fila", pane, texto)


def nomear(pane: str, nome: str, id: str | None = None) -> str:
    """Name the pane 'ID - nome' (next free TNN/HNN when id is None); returns the id."""
    return _run("nomear", pane, nome, *([id] if id else [])).strip()


def abrir(pasta: str, nome: str, comando: str) -> str:
    """Open a pane to the right without taking focus, run the command, name it; returns the id."""
    return _run("abrir", pasta, nome, comando).strip()


# --- the live state, from the local NATS JetStream (kept by dev/prime-bili/vigia.py) ---

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")


async def estado() -> list[dict]:
    """Every pane as the vigia last saw it (KV mesa_panes): id, mux, pane, nome, estado, fase, aba, desde."""
    import json
    import nats

    nc = await nats.connect(NATS_URL)
    try:
        kv = await nc.jetstream().key_value("mesa_panes")
        try:
            keys = await kv.keys()
        except Exception:
            return []
        return [json.loads((await kv.get(k)).value) for k in keys]
    finally:
        await nc.close()


async def eventos(n: int = 20) -> list[dict]:
    """The last n changes from the MESA stream (subject, em, antes, depois), oldest first."""
    import json
    import nats

    nc = await nats.connect(NATS_URL)
    try:
        js = nc.jetstream()
        last = (await js.stream_info("MESA")).state.last_seq
        out = []
        for seq in range(max(1, last - n + 1), last + 1):
            try:
                m = await js.get_msg("MESA", seq)
            except Exception:
                continue
            if m.subject.startswith("mesa.pane."):
                out.append({"subject": m.subject, **json.loads(m.data)})
        return out
    finally:
        await nc.close()
