"""Tensions as a dev-console project: what the console needs to show this project.

Run: uv run --script ../../dev-console/scripts/dev-console.py --project scripts/dev_console_project.py
The console imports this file; fasthtml comes from the console's own environment.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from app_tensions import Tensions  # noqa: E402
from fasthtml.common import Div, Li, P, Span, Ul  # noqa: E402

NAME = "Tensions"
SOURCE = Path(__file__).parent / "app_tensions.py"  # the file with the command registry, EVENTS
ENTITY = "Tension"                                   # what one item of the rail is
ENTITY_PLURAL = "tensões"
ENTITIES = {"management": "Tension", "observation": "Observation", "relationship": "Relationship", "action": "Action"}
ENTITY_KEY = "tension_id"                            # the journal field that names the entity
PROJECTOR = "_project"                               # function that folds events into the entity (its dict literal = the properties)
journal = Tensions()


def title_of(history: list[dict], state: dict) -> str:
    created = next((e for e in history if e["event"] == "management.created"), None)
    return (created or {}).get("value", {}).get("title") or state.get("actual", "")


# --- widgets: event -> views. Each takes the console's EventContext (ctx) and returns a component. ---

def when(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")


def field(label: str, value: Any):
    return Div(Span(label, cls="w-24 shrink-0 text-neutral-400"),
               Span(str(value), cls="min-w-0 font-sans text-sm text-neutral-800 dark:text-neutral-200"),
               cls="flex gap-3 py-1")


def tension_list(ctx):
    """Every Tension in the journal; the current one marked."""
    return Ul(*[
        Li(Span("●" if t["id"] == ctx.entity_id else "○", cls="w-4 shrink-0 text-neutral-500"),
           Div(P(t.get("title") or t["actual"], cls="truncate font-sans text-sm "
                 + ("font-semibold text-neutral-900 dark:text-neutral-100" if t["id"] == ctx.entity_id
                    else "text-neutral-600 dark:text-neutral-400")),
               P(f'{t["status"]} · {t["event_count"]} eventos · {when(t["updated_at"])}', cls="text-neutral-400"),
               cls="min-w-0"),
           cls="flex gap-2 py-1.5")
        for t in sorted(ctx.entities, key=lambda t: t["updated_at"], reverse=True)
    ])


def tension_detail(ctx):
    """The projected Tension: the gap and its context."""
    s = ctx.state
    return Div(
        field("hoje", s["actual"]), field("desejado", s["desired"]),
        *[field(k, v) for k, v in (s.get("context") or {}).items()],
        field("criada", when(s.get("created_at", s["updated_at"]))), field("atualizada", when(s["updated_at"])),
        field("estado", s["status"]), field("eventos", s["event_count"]),
    )


def tension_updates(ctx):
    """Each update: what changed and why."""
    return Ul(*[
        Li(P(f'{when(e["at"])} · {e["actor"]}', cls="text-neutral-400"),
           *[field(k, e["value"][k]) for k in ("actual", "desired", "context") if k in e["value"]],
           P(e["value"].get("reason", ""), cls="text-neutral-500"), cls="py-2")
        for e in reversed(ctx.events)
    ])


def observation_list(ctx):
    """What was observed, newest first, with source and time."""
    return Ul(*[
        Li(P(e["value"].get("value") or e["value"].get("observation", ""), cls="font-sans text-sm text-neutral-800 dark:text-neutral-200"),
           P(f'{e["value"].get("source", e["actor"])} · {when(e["value"].get("observed_at", e["at"]))}', cls="text-neutral-400"),
           cls="py-2 border-b border-neutral-100 dark:border-neutral-900 last:border-0")
        for e in reversed(ctx.events)
    ])


def linked_items(ctx):
    """What this Tension is linked to."""
    return Ul(*[
        Li(Span(e["value"]["target"], cls="w-20 shrink-0 font-semibold"),
           Span(e["value"].get("title", ""), cls="min-w-0 truncate font-sans text-sm text-neutral-700 dark:text-neutral-300"),
           cls="flex gap-3 py-1")
        for e in ctx.events
    ])


def proposal_list(ctx):
    """The proposed actions, in order."""
    return Ul(*[
        Li(Span(f"{n}.", cls="w-6 shrink-0 text-neutral-400"),
           Span(e["value"].get("proposal", ""), cls="min-w-0 font-sans text-sm text-neutral-800 dark:text-neutral-200"),
           cls="flex gap-2 py-2")
        for n, e in enumerate(ctx.events, 1)
    ])


WIDGETS = {
    "management.created": [tension_list, tension_detail],
    "management.updated": [tension_updates],
    "observation.recorded": [observation_list],
    "relationship.linked": [linked_items],
    "action.proposed": [proposal_list],
}
