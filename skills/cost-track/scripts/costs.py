# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Costs: everything is monetary, everything has a cost. Design stage (draft), drawn in the dev-console.

Gabriel prices his own time. Every domain he works in belongs to a cost center (accounting's term): a client that
pays and has a day budget, or an investment with no budget but a cost. While the clock runs in a domain, the time
goes to that domain's cost center, priced at what he is worth. The record of one focus stretch is a time entry
(the timesheet's term); the day's cost per center is the sum of its entries.

Prototype: the journal is a global append-only JSONL, ~/.local/share/costs/events.jsonl (override COSTS_DIR),
easy to edit by hand. This file is the only writer of it:

    uv run --script costs.py emit <event> '<json value>' [--cost-center <id>] [--actor <who>]
    uv run --script costs.py bind <center> <domain>   # the domain prices in that center (idempotent)

and the module API the dev-console imports: worth(), centers(), center_of(), rate_hour(), budget_day(), today().
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def costs_dir() -> Path:
    """The folder of the journal (and of the running stretch); read on every call so COSTS_DIR may change."""
    return Path(os.environ.get("COSTS_DIR", "~/.local/share/costs")).expanduser()


def journal_path() -> Path:
    return costs_dir() / "events.jsonl"

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
        return events()

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


# --- the journal: the one writer, and the reads the dev-console's money bar uses -----------------------------------
KNOWN_EVENTS = [f"{cat}.{ev}" for cat, cmds in EVENTS.items() for ev in dict.fromkeys(cmds.values())]
DEFAULT_PAID_HOURS_DAY, DEFAULT_WORK_DAYS_MONTH = 5, 21


def events() -> list[dict]:
    """Every event of the journal, oldest first; a line that is not JSON is skipped."""
    path = journal_path()
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _now() -> datetime:
    return datetime.now().astimezone()


def emit(event: str, value: dict, cost_center: str | None = None, actor: str = "agent", at: datetime | None = None) -> dict:
    """Append one event to the journal (id and `at` generated) and return it. The only writer of the Costs journal."""
    if event not in KNOWN_EVENTS:
        raise ValueError(f"unknown event {event!r}; known: {', '.join(KNOWN_EVENTS)}")
    if not isinstance(value, dict):
        raise ValueError("the value must be a JSON object")
    if event != "worth.updated" and not cost_center:
        raise ValueError(f"{event} needs a cost center")
    e: dict[str, Any] = {"id": uuid.uuid4().hex[:12], "event": event}
    if cost_center:
        e["cost_center"] = cost_center
    e.update(at=(at or _now()).isoformat(timespec="seconds"), actor=actor, value=value)
    path = journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e


def worth() -> dict:
    """The value of the latest `worth.updated` ({} when he never said)."""
    ws = [e for e in events() if e["event"] == "worth.updated"]
    return ws[-1].get("value", {}) if ws else {}


def centers() -> dict[str, dict]:
    """The latest value per cost center id."""
    out: dict[str, dict] = {}
    for e in events():
        if e["event"] == "cost_center.updated" and e.get("cost_center"):
            out[e["cost_center"]] = e.get("value", {})
    return out


def center_of(slug: str, declared: str | None = None) -> str | None:
    """The cost center of a domain: the COST_CENTER its project declares (when the journal knows it), else the center
    whose `domains` lists the slug, else None."""
    known = centers()
    if declared and declared in known:
        return declared
    return next((cid for cid, v in known.items() if slug in v.get("domains", [])), None)


def bind(center: str, domain: str, actor: str = "agent") -> dict | None:
    """Bind a domain to a cost center: a `cost_center.updated` with the center's last value plus the domain in
    `domains`. None (no event) when it is already bound there; ValueError when the center is unknown. A domain has one
    center: it leaves any other center's `domains` first (same rule, one event each)."""
    known = centers()
    if center not in known:
        raise ValueError(f"unknown cost center {center!r}; known: {', '.join(sorted(known)) or '(none)'}")
    for cid, v in known.items():
        if cid != center and domain in v.get("domains", []):
            emit("cost_center.updated", {**v, "domains": [d for d in v["domains"] if d != domain]}, cid, actor)
    v = known[center]
    if domain in v.get("domains", []):
        return None
    return emit("cost_center.updated", {**v, "domains": [*v.get("domains", []), domain]}, center, actor)


def _hours_month(w: dict) -> float:
    return w.get("paid_hours_day", DEFAULT_PAID_HOURS_DAY) * w.get("work_days_month", DEFAULT_WORK_DAYS_MONTH)


def rate_hour(center: str) -> float | None:
    """R$ per hour: a client is charged at what he is worth now (`value_month`), an investment at the goal
    (`goal_month`), over `paid_hours_day x work_days_month`. None when the center or the worth is unknown."""
    c, w = centers().get(center), worth()
    if not c or not w:
        return None
    month = w.get("goal_month") if c.get("kind") == "investment" else w.get("value_month")
    return month / _hours_month(w) if month else None


def budget_day(center: str) -> float | None:
    """What a client pays per work day (`pays_month / work_days_month`); None for an investment (no budget)."""
    c = centers().get(center)
    if not c or c.get("kind") != "client":
        return None
    if c.get("pays_month"):
        return c["pays_month"] / worth().get("work_days_month", DEFAULT_WORK_DAYS_MONTH)
    return c.get("budget_day")


def today_by_center(now: datetime | None = None) -> dict[str, tuple[int, float]]:
    """{center: (seconds, cost)} of today's `time_entry.stopped` (today = the local date of `at`)."""
    day = (now or _now()).astimezone().date()
    out: dict[str, tuple[int, float]] = {}
    for e in events():
        if e["event"] != "time_entry.stopped" or not e.get("cost_center"):
            continue
        if datetime.fromisoformat(e["at"]).astimezone().date() != day:
            continue
        sec, cost = out.get(e["cost_center"], (0, 0.0))
        v = e.get("value", {})
        out[e["cost_center"]] = (sec + int(v.get("seconds", 0)), round(cost + v.get("cost", 0.0), 2))
    return out


def today(center: str, now: datetime | None = None) -> tuple[int, float]:
    """(seconds, cost in R$) of today's stopped entries of one cost center."""
    return today_by_center(now).get(center, (0, 0.0))


# --- the running stretch: survives a hot reload of the console (a file in the costs folder, not an event) ----------
def running() -> dict | None:
    try:
        return json.loads((costs_dir() / "running.json").read_text())
    except (OSError, ValueError):
        return None


def set_running(state: dict | None) -> None:
    path = costs_dir() / "running.json"
    if state is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))


# --- the sentences a person reads in the journal --------------------------------------------------------------------
def brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def hm(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 3600}h{s % 3600 // 60:02d}"


def started_text(center: str, domain: str) -> str:
    name = centers().get(center, {}).get("name", center)
    return f"Relógio ligado no domínio {domain}, do centro {name}."


def stopped_text(center: str, domain: str, seconds: float, cost: float) -> str:
    c = centers().get(center, {})
    name = c.get("name", center)
    if c.get("kind") == "investment":
        return f"{hm(seconds)} investidas em {name} ({domain}), {brl(cost)} pelo preço da meta."
    b = budget_day(center)
    return f"{hm(seconds)} na {name} ({domain}), {brl(cost)}" + (f" do orçamento de {brl(b)}." if b else ".")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the only writer of the Costs journal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    em = sub.add_parser("emit", help="append one event")
    em.add_argument("event", help="e.g. worth.updated, cost_center.updated, time_entry.started, time_entry.stopped")
    em.add_argument("value", help="the event's value, a JSON object")
    em.add_argument("--cost-center", default=None)
    em.add_argument("--actor", default="agent")
    bd = sub.add_parser("bind", help="bind a domain to a cost center (cost_center.updated with the domain in `domains`)")
    bd.add_argument("center")
    bd.add_argument("domain")
    bd.add_argument("--actor", default="agent")
    args = ap.parse_args(argv)
    if args.cmd == "bind":
        try:
            e = bind(args.center, args.domain, args.actor)
        except ValueError as err:
            print(f"costs: {err}", file=sys.stderr)
            return 1
        print(json.dumps(e, ensure_ascii=False) if e else f"{args.domain} already in {args.center}")
        return 0
    try:
        value = json.loads(args.value)
        e = emit(args.event, value, args.cost_center, args.actor)
    except ValueError as err:
        print(f"costs: {err}", file=sys.stderr)
        return 1
    print(json.dumps(e, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
