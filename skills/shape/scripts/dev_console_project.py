"""Shape in the dev-console: every request walked through routing, backbrief and delegation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fasthtml.common import Div, P, Span  # noqa: E402
from shape import TRANSITIONS, ShapeJournal  # noqa: E402,F401

NAME = "Biliboss Skills - Shape"
SLUG = "shape"
SOURCE = Path(__file__).parent / "shape.py"  # the file with EVENTS
ENTITY = "Shaping"
ENTITY_PLURAL = "modelagens"
ENTITIES = {"request": "Request", "piece": "Piece", "understanding": "Understanding", "work": "Work"}
ENTITY_KEY = "shaping"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = ShapeJournal()

# The owner asks for something.
INITIAL = ["request.received"]

BORDO = "#800020"  # the only colour: what waits for the owner
MARKS = {
    "received": ("○", "recebido", False),
    "routed": ("○", "roteado", False),
    "taught_back": ("◆", "backbrief pendente", True),
    "confirmed": ("●", "confirmado", False),
    "delegated": ("●", "delegado", False),
}


def title_of(history: list[dict], state: dict) -> str:
    return state.get("request") or state.get("id", "")


def modelagens(ctx):
    """Every shaping, one line each: request · piece · state; burgundy only for what waits for the owner."""
    rows = sorted(ctx.entities, key=lambda s: s.get("updated_at", ""), reverse=True)
    head = P("Modelagens", cls="font-sans text-lg font-semibold text-neutral-900 dark:text-neutral-100")
    if not rows:
        return Div(head, P("Nenhuma modelagem ainda.", cls="text-neutral-400"))
    lines = []
    for s in rows:
        glyph, text, owner = MARKS.get(s.get("status", "received"), MARKS["received"])
        lines.append(Div(
            Span(s.get("request", ""), cls="min-w-0 flex-1 truncate font-semibold text-neutral-900 dark:text-neutral-100"),
            Span(s.get("piece") or "·", cls="w-28 shrink-0 text-neutral-400"),
            Span(f"{glyph} {text}", cls="w-44 shrink-0", style=f"color:{BORDO}" if owner else "color:#9a9a9a"),
            cls="flex gap-3 py-1 font-mono text-sm"))
    return Div(head, Div(*lines, cls="mt-2"), data_modelagens="1")


WIDGETS = {e: [modelagens] for e in
           ("request.received", "piece.routed", "understanding.taught_back", "understanding.confirmed",
            "work.delegated")}
HOME = ("request.received", "Modelagens")
