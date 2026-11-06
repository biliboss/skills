"""Brainstorm in the dev-console: an open idea thought through in a Double Diamond; the causal loop is drawn as a graph."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fasthtml.common import Div, Li, P, Script, Span, Ul  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "dev-console" / "scripts"))  # the console's atoms
from console_atoms import empty, title  # noqa: E402
from brainstorm import TRANSITIONS, BrainstormJournal, causal_graph  # noqa: E402,F401

NAME = "Biliboss Skills - Brainstorm"
SLUG = "brainstorm"
SOURCE = Path(__file__).parent / "brainstorm.py"  # the file with EVENTS
ENTITY = "Session"
ENTITY_PLURAL = "sessões"
ENTITIES = {"session": "Session", "problem": "Problem", "question": "Question", "variable": "Variable",
            "link": "Link", "loop": "Loop", "approach": "Approach", "leverage": "Leverage"}
ENTITY_KEY = "session"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = BrainstormJournal()

# The owner opens a brainstorm.
INITIAL = ["session.started"]


def title_of(history: list[dict], state: dict) -> str:
    return state.get("idea") or state.get("id", "")


def _elements(g: dict) -> list[dict]:
    """Cytoscape elements: variables on a circle, links as arrows labelled + or -; the simplest graph the console
    already supports (a widget with a cytoscape box, as backbrief's Skill widget)."""
    import math

    n = max(len(g["nodes"]), 1)
    r = 40 + 38 * n
    els = []
    for i, name in enumerate(g["nodes"]):
        a = 2 * math.pi * i / n - math.pi / 2
        els.append({"data": {"id": name, "label": name}, "position": {"x": round(r * math.cos(a)), "y": round(r * math.sin(a))}})
    for i, e in enumerate(g["edges"]):
        els.append({"data": {"id": f"e{i}", "source": e["from"], "target": e["to"],
                             "label": "+" if e["polarity"] == "+" else "\u2212"},
                    "classes": "pos" if e["polarity"] == "+" else "neg"})
    return els


def causal_loop(ctx):
    """Causal Loop: the session's variables as nodes, links as arrows labelled + or -, and the R / B loops found."""
    import json

    g = causal_graph(ctx.history or [])
    els = json.dumps(_elements(g), ensure_ascii=False).replace("</", "<\\/")
    script = """
(() => {
  const box = document.getElementById('causal-loop-cy'); if (!box || !window.cytoscape) return;
  const dark = matchMedia('(prefers-color-scheme: dark)').matches, fg = dark ? '#e5e5e5' : '#262626',
        line = dark ? '#525252' : '#a3a3a3', pos = '#4ade80', neg = '#f87171';
  const cy = cytoscape({container: box, elements: ELS, layout: {name: 'preset', fit: true, padding: 40},
    userZoomingEnabled: false, userPanningEnabled: false, boxSelectionEnabled: false, autoungrabify: true,
    style: [
      {selector: 'node', style: {label: 'data(label)', 'text-valign': 'center', 'text-halign': 'center',
        'font-family': 'ui-monospace, monospace', 'font-size': 12, color: fg, shape: 'round-rectangle',
        width: 130, height: 34, 'background-color': dark ? '#171717' : '#fafafa', 'border-width': 1.5, 'border-color': line}},
      {selector: 'edge', style: {width: 2, 'line-color': line, 'target-arrow-color': line, 'target-arrow-shape': 'triangle',
        'curve-style': 'bezier', 'control-point-step-size': 50, label: 'data(label)', 'font-size': 18, 'font-weight': 'bold',
        color: fg, 'text-background-opacity': 1, 'text-background-color': dark ? '#0a0a0a' : '#fff', 'text-background-padding': 2}},
      {selector: 'edge.pos', style: {'line-color': pos, 'target-arrow-color': pos}},
      {selector: 'edge.neg', style: {'line-color': neg, 'target-arrow-color': neg}},
    ]});
  window.__brainstorm_cy = cy;
  new ResizeObserver(() => { if (box.clientWidth && box.clientHeight) { cy.resize(); cy.fit(undefined, 40); } }).observe(box);
})();
""".replace("ELS", els)
    loops = [Li(Span(f"{l['kind']}", cls="font-mono text-sm font-semibold"),
                Span(" " + " \u2192 ".join(l["variables"]), cls="text-neutral-500"), cls="mt-1")
             for l in g["loops"]]
    return Div(
        title("Laço causal"),
        Div(id="causal-loop-cy", cls="h-[420px] w-full rounded border border-neutral-200 dark:border-neutral-800")
        if g["nodes"] else empty("nenhuma variável nesta sessão ainda"),
        Ul(*loops, cls="mt-3") if loops else "",
        P("R reforça (bola de neve), B equilibra (busca uma meta); + mesmo sentido, − sentido oposto.",
          cls="mt-3 text-xs text-neutral-400"),
        Script(script) if g["nodes"] else "",
        cls="p-5 w-[min(860px,86vw)]",
    )


WIDGETS = {
    "link.added": [causal_loop],
    "loop.identified": [causal_loop],
}
HOME = ("link.added", "CausalLoop")
