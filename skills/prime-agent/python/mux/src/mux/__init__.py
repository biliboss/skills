"""mux: tmux and herdr panes from the Prime Agent REPL, as thin wrappers over the prime-agent skill's mux.sh.

mux.sh holds the logic (ids TNN/HNN, which multiplexer owns a pane); these functions only call it, so the
shell and the REPL behave the same.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

def _find_mux_sh() -> Path:
    """$MUX_SH, else the skill folder this file sits in (python/mux/src/mux/), else the installed plugin, else
    the source clone. The kernel may run an installed copy of this package, far from the skill folder."""
    if os.environ.get("MUX_SH"):
        return Path(os.environ["MUX_SH"])
    here = Path(__file__).resolve()
    cands = [here.parents[4] / "scripts" / "mux.sh"] if len(here.parents) > 4 else []
    home = Path.home()
    cands += sorted(home.glob(".claude*/plugins/cache/biliboss/biliboss-skills/*/skills/prime-agent/scripts/mux.sh"), reverse=True)
    cands.append(home / "src/skills/skills/prime-agent/scripts/mux.sh")
    for c in cands:
        if c.is_file():
            return c
    raise RuntimeError("mux: não achei o mux.sh da skill prime-agent; defina MUX_SH")


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


def manda(pane: str, texto: str) -> None:
    """Paste the text as one message and press Enter."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(texto)
        path = f.name
    try:
        _run("manda", pane, path)
    finally:
        os.unlink(path)


def nomear(pane: str, nome: str, id: str | None = None) -> str:
    """Name the pane 'ID - nome' (next free TNN/HNN when id is None); returns the id."""
    return _run("nomear", pane, nome, *([id] if id else [])).strip()


def abrir(pasta: str, nome: str, comando: str) -> str:
    """Open a pane to the right without taking focus, run the command, name it; returns the id."""
    return _run("abrir", pasta, nome, comando).strip()
