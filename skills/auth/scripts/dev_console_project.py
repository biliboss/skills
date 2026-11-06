"""Auth in the dev-console: the agent's secure identity, accounts per provider (design stage)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from auth import TRANSITIONS, AuthJournal  # noqa: E402,F401
from fasthtml.common import Div, P, Span  # noqa: E402

NAME = "Biliboss Skills - Auth"
SLUG = "auth"
SOURCE = Path(__file__).parent / "auth.py"  # the file with EVENTS
ENTITY = "Account"
ENTITY_PLURAL = "contas"
ENTITIES = {"provider": "Provider", "account": "Account"}
ENTITY_KEY = "account"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = AuthJournal()

# The owner (or the agent for him) sets up a provider: its OAuth client goes into envless.
INITIAL = ["provider.updated"]

BORDO = "#7a1f2b"  # the only colour: what needs the owner
MARKS = {"ok": ("●", "ok", False), "needs_login": ("◆", "precisa de login", True), "broken": ("✗", "quebrada", True)}


def title_of(history: list[dict], state: dict) -> str:
    return state.get("alias") or state.get("id", "")


def contas(ctx):
    """Every account, one line each: provider · alias · email · state; burgundy only for what needs the owner."""
    rows = sorted(ctx.entities, key=lambda s: (s.get("provider", ""), s.get("alias", "")))
    if not rows:
        return Div(P("Contas", cls="font-sans text-lg font-semibold"), P("Nenhuma conta ainda.", cls="text-neutral-400"))
    lines = []
    for s in rows:
        glyph, text, owner = MARKS.get(s.get("status", "needs_login"), MARKS["broken"])
        lines.append(Div(
            Span(s.get("provider", ""), cls="w-16 shrink-0 text-neutral-400"),
            Span(s.get("alias", ""), cls="w-24 shrink-0 font-semibold text-neutral-900 dark:text-neutral-100"),
            Span(s.get("email", ""), cls="min-w-0 flex-1 truncate text-neutral-500"),
            Span(f"{glyph} {text}", cls="shrink-0", style=f"color:{BORDO}" if owner else "color:#9a9a9a"),
            cls="flex gap-3 py-1 font-mono text-sm"))
    return Div(P("Contas", cls="font-sans text-lg font-semibold text-neutral-900 dark:text-neutral-100"),
               Div(*lines, cls="mt-2"), data_contas="1")


WIDGETS = {"account.updated": [contas], "account.checked": [contas], "account.connected": [contas]}
HOME = ("account.updated", "Contas")
