# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""shape: the journal of the planning door. One shaping is one request walked through context, routing, backbrief and
delegation (Shape Up: shape the work before betting on it). Drawn in the dev-console as the Shape domain.

The journal is a global append-only JSONL, ~/.local/share/shape/events.jsonl (override SHAPE_DIR); the only writer is
`emit` here (through shape.sh).
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

EVENTS = {
    "request": {
        # O dono pediu algo (construir, escrever, mudar, decidir): nasce uma modelagem.
        "receive": "received",
    },
    "piece": {
        # A peça de planejamento escolhida pelo tipo do pedido (ou direct, quando o pedido é claro e pequeno).
        "route": "routed",
    },
    "understanding": {
        # O backbrief: o agente repetiu o pedido ao dono com as próprias palavras. Espera o ok dele.
        "teach_back": "taught_back",
        # O dono confirmou (ou corrigiu): só agora se constrói.
        "confirm": "confirmed",
    },
    "work": {
        # O trabalho saiu: subagente (minutos), thread (tópico que vive) ou card no Upstream.
        "delegate": "delegated",
    },
}

TRANSITIONS = {
    "request.received": ["piece.routed"],
    "piece.routed": ["understanding.taught_back"],
    "understanding.taught_back": ["understanding.taught_back", "understanding.confirmed"],
    "understanding.confirmed": ["work.delegated"],
}

PIECES = ("brainstorm", "pelo-resultado", "interview", "domain-plan", "design-taste", "direct")
DELEGATIONS = ("subagent", "thread", "card")


def _project(events: list[dict]) -> dict:
    """A shaping as the journal leaves it: the request, the piece, how far it got, where the work went."""
    if not events:
        return {}
    s = {"id": events[-1]["shaping"], "request": "", "piece": "", "status": "received", "delegated_to": "",
         "updated_at": events[-1]["at"]}
    for e in events:
        v = e.get("value", {})
        kind = e["event"]
        if kind == "request.received":
            s["request"] = v.get("text", "")
        elif kind == "piece.routed":
            s["piece"] = v.get("piece", "")
        elif kind == "work.delegated":
            s["delegated_to"] = v.get("to", "")
        s["status"] = kind.split(".")[1]
    return s


class ShapeJournal:
    """Read-only view of the Shape journal for the dev-console contract."""

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        events = _all_events()
        if "id" in query:
            matches = [e for e in events if e.get("shaping") == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        return shapings()


def journal_path() -> Path:
    """The journal, read from SHAPE_DIR on every call."""
    return Path(os.environ.get("SHAPE_DIR", "~/.local/share/shape")).expanduser() / "events.jsonl"


def _all_events() -> list[dict]:
    p = journal_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def validate(event: str, value: dict) -> None:
    if event == "piece.routed":
        if value.get("piece") not in PIECES:
            raise ValueError(f"value.piece must be one of {PIECES}")
    elif event == "work.delegated":
        if value.get("to") not in DELEGATIONS:
            raise ValueError(f"value.to must be one of {DELEGATIONS}")
    elif not value.get("text"):
        raise ValueError("value needs a non-empty `text`")


def emit(event: str, value: dict, shaping: str, actor: str = "agent") -> dict:
    valid = {f"{d}.{k}" for d, kinds in EVENTS.items() for k in kinds.values()}
    if event not in valid:
        raise ValueError(f"unknown event {event!r}; one of {sorted(valid)}")
    if not isinstance(value, dict):
        raise ValueError("value must be a JSON object")
    if not shaping:
        raise ValueError(f"{event} requires --shaping <id>")
    validate(event, value)
    row: dict[str, Any] = {"id": uuid.uuid4().hex[:12], "event": event, "shaping": shaping,
                           "at": datetime.now().astimezone().isoformat(timespec="seconds"), "actor": actor,
                           "value": value}
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def shapings(status: str | None = None) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for e in _all_events():
        if e.get("shaping"):
            groups.setdefault(e["shaping"], []).append(e)
    out = [s for g in groups.values() if (s := _project(g))]
    return [s for s in out if not status or s["status"] == status]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shape.py", description="Shape journal: the only writer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("event")
    e.add_argument("value")
    e.add_argument("--shaping", required=True)
    e.add_argument("--actor", required=True)
    s = sub.add_parser("list")
    s.add_argument("--status")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            print(json.dumps(emit(a.event, json.loads(a.value), a.shaping, a.actor), ensure_ascii=False))
        else:
            print(json.dumps(shapings(a.status), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
