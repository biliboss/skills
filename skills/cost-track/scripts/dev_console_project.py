"""Costs in the dev-console: everything is monetary, everything has a cost (design stage)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fasthtml.common import H2, Div, P, Span  # noqa: E402
from costs import TRANSITIONS, CostsJournal  # noqa: E402,F401

NAME = "Biliboss Skills - Costs"
SLUG = "costs"
SOURCE = Path(__file__).parent / "costs.py"  # the file with EVENTS
ENTITY = "CostCenter"
ENTITY_PLURAL = "centros de custo"
ENTITIES = {"worth": "Worth", "cost_center": "CostCenter", "time_entry": "TimeEntry"}
ENTITY_KEY = "cost_center"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = CostsJournal()

# The Human starts by saying what he is worth.
INITIAL = ["worth.updated"]


def title_of(history: list[dict], state: dict) -> str:
    return state.get("name") or state.get("id", "")


# --- widgets: real data from the journal, for a person (the sentence and the money) -----------------------------


def _title(text: str):
    """Every widget starts with its title."""
    return H2(text, cls="mb-3 font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100")


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _hm(sec: int) -> str:
    return f"{sec // 3600}h{sec % 3600 // 60:02d}"


def _worth(ctx) -> dict:
    ws = [e for e in ctx.journal_events if e["event"] == "worth.updated"] or journal.read({"event": "worth.updated"})
    return ws[-1]["value"] if ws else {}


def worth(ctx):
    """Worth: what your hour costs now and at the goal."""
    w = _worth(ctx)
    hours = w.get("paid_hours_day", 5) * w.get("work_days_month", 21)
    now, goal = w.get("value_month", 0) / hours, w.get("goal_month", 0) / hours
    row = lambda k, v, sub: Div(Span(k, cls="text-neutral-500"), Span(v, cls="tabular-nums font-semibold text-neutral-900 dark:text-neutral-100"),
                                Span(sub, cls="tabular-nums text-neutral-400"), cls="grid grid-cols-[8rem_7rem_1fr] gap-2 py-1")
    return Div(_title("Quanto vale a sua hora"),
               row("agora", _brl(now), f"{_brl(now / 60)}/min · {_brl(w.get('value_month', 0))}/mês"),
               row("na meta", _brl(goal), f"{_brl(goal / 60)}/min · {_brl(w.get('goal_month', 0))}/mês"),
               P("Clientes pagam o preço de agora; investimento custa o preço da meta.", cls="mt-2 text-sm text-neutral-400"))


def cost_centers(ctx):
    """Cost Centers: each center, its kind, its day budget and what it cost."""
    rows = []
    for c in sorted(ctx.entities, key=lambda c: (c.get("kind") != "client", c.get("name", ""))):
        kind = "cliente" if c.get("kind") == "client" else "investimento"
        budget = f"de {_brl(c['budget_day'])}/dia" if c.get("budget_day") else "sem teto"
        rows.append(Div(Span(c.get("name", c["id"]), cls="font-semibold text-neutral-900 dark:text-neutral-100"),
                        Span(kind, cls="text-neutral-500"), Span(budget, cls="tabular-nums text-neutral-400"),
                        Span(_brl(c.get("cost", 0)), cls="tabular-nums text-right text-neutral-800 dark:text-neutral-200"),
                        cls="grid grid-cols-[9rem_7rem_1fr_7rem] gap-2 py-1"))
    return Div(_title("Centros de custo"), *rows) if rows else Div(_title("Centros de custo"), P("nenhum centro ainda", cls="text-neutral-400"))


def day_cost(ctx):
    """Day Cost: where today's time went, in money, per cost center."""
    stops = [e for e in journal.read({"event": "time_entry.stopped"})]
    day = max((e["at"][:10] for e in stops), default="")
    names = {c["id"]: c for c in journal.read({})}
    tot: dict[str, list] = {}
    for e in stops:
        if e["at"][:10] == day:
            t = tot.setdefault(e["cost_center"], [0, 0.0])
            t[0] += e["value"].get("seconds", 0)
            t[1] += e["value"].get("cost", 0.0)
    rows = []
    for cid, (sec, cost) in sorted(tot.items(), key=lambda kv: -kv[1][1]):
        c = names.get(cid, {})
        over = c.get("budget_day") and cost > c["budget_day"]
        rows.append(Div(Span(c.get("name", cid), cls="text-neutral-700 dark:text-neutral-300"),
                        Span(_hm(sec), cls="tabular-nums text-neutral-400"),
                        Span(_brl(cost), cls="tabular-nums text-right font-semibold " + ("text-red-500" if over else "text-neutral-900 dark:text-neutral-100")),
                        Span(f"de {_brl(c['budget_day'])}" if c.get("budget_day") else "investido", cls="tabular-nums text-neutral-400"),
                        cls="grid grid-cols-[9rem_4rem_7rem_1fr] gap-2 py-1"))
    total = sum(v[1] for v in tot.values())
    return Div(_title("Para onde foi o seu tempo hoje"), *rows,
               Div(Span("total", cls="text-neutral-500"), Span(_hm(sum(v[0] for v in tot.values())), cls="tabular-nums text-neutral-400"),
                   Span(_brl(total), cls="tabular-nums text-right font-semibold text-neutral-900 dark:text-neutral-100"), Span(""),
                   cls="grid grid-cols-[9rem_4rem_7rem_1fr] gap-2 pt-2 mt-1 border-t border-neutral-200 dark:border-neutral-800"))


def time_entries(ctx):
    """Time Entries: each stretch of this cost center, as a sentence."""
    es = [e for e in ctx.events] or [e for e in journal.read({"event": "time_entry.stopped"})]
    return Div(_title("Trechos de tempo"),
               *[Div(P(e["value"].get("text", ""), cls="text-neutral-800 dark:text-neutral-200"),
                     P(e["at"][11:16], cls="text-xs text-neutral-400"), cls="py-1.5") for e in es])


WIDGETS: dict = {
    "worth.updated": [worth],
    "cost_center.updated": [cost_centers],
    "time_entry.stopped": [day_cost, time_entries],
}
HOME = ("time_entry.stopped", "DayCost")
