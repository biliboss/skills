"""Costs: everything is monetary, everything has a cost. Design stage (draft), drawn in the dev-console.

Gabriel prices his own time. Every domain he works in belongs to a cost center (accounting's term): a client that
pays and has a day budget, or an investment with no budget but a cost. While the clock runs in a domain, the time
goes to that domain's cost center, priced at what he is worth. The record of one focus stretch is a time entry
(the timesheet's term); the day's cost per center is the sum of its entries.

Prototype: the journal is a global append-only JSONL, ~/.local/share/costs/events.jsonl (override COSTS_DIR),
easy to edit by hand.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

JOURNAL = Path(os.environ.get("COSTS_DIR", "~/.local/share/costs")).expanduser() / "events.jsonl"

EVENTS = {
    # Quanto você vale: o valor de agora por mês (R$ 20 mil), a meta (R$ 50 mil) e as horas pagas por dia. Dele sai o
    # preço da hora; mudar o valor não reescreve o que já foi gasto.
    "worth": {"update": "updated"},
    # Um centro de custo foi criado ou mudou: um cliente, que paga e tem orçamento por dia (Mukutu, Unicred), ou um
    # investimento, sem orçamento mas com custo, cobrado pelo preço da meta (Via Corretor, Biliboss Skills). Cada
    # domínio do dev-console diz de que centro é.
    "cost_center": {"update": "updated"},
    "time_entry": {
        # Você ligou o relógio num domínio: o tempo começou a contar para o centro de custo dele.
        "start": "started",
        # O relógio parou (você pausou, trocou de domínio, escondeu a janela ou ficou 5 min sem mexer no Mac): o trecho
        # virou uma entrada de tempo, com os segundos, o preço da hora usado e o custo em reais.
        "stop": "stopped",
    },
}

# The edges, in the order the story happens: you say what you are worth, set the cost centers, then the clock runs.
TRANSITIONS = {
    "worth.updated": ["cost_center.updated"],
    "cost_center.updated": ["time_entry.started"],
    "time_entry.started": ["time_entry.stopped"],
    "time_entry.stopped": ["time_entry.started"],
}


def _project(events: list[dict]) -> dict:
    """A cost center as the journal leaves it: what it is and what it cost."""
    if not events:
        return {}
    v = events[-1]
    state = {
        "id": v["cost_center"],
        "name": "",
        "kind": "",
        "budget_day": None,
        "seconds": 0,
        "cost": 0.0,
        "updated_at": v["at"],
    }
    for e in events:
        val = e.get("value", {})
        if e["event"] == "cost_center.updated":
            state.update(name=val.get("name", ""), kind=val.get("kind", ""), budget_day=val.get("budget_day"))
        if e["event"] == "time_entry.stopped":
            state["seconds"] += val.get("seconds", 0)
            state["cost"] = round(state["cost"] + val.get("cost", 0.0), 2)
    return state


class CostsJournal:
    """Read-only view of costs.jsonl for the dev-console contract."""

    def _events(self) -> list[dict]:
        if not JOURNAL.exists():
            return []
        return [json.loads(line) for line in JOURNAL.read_text().splitlines() if line.strip()]

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        events = self._events()
        if "id" in query:
            matches = [e for e in events if e.get("cost_center") == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for e in events:
            if e.get("cost_center"):
                groups.setdefault(e["cost_center"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]
