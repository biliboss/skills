# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Brainstorm: thinking with the owner while an idea is still open, inside a Double Diamond (discover, define,
develop, deliver), with systems-thinking tools (Cynefin, iceberg, causal loops, leverage points). Drawn in the
dev-console as the Brainstorm domain.

Names come from the literature: Osborn's brainstorming (1953), the Design Council's Double Diamond (2005), Snowden's
Cynefin, Forrester and Senge's causal loops (+ / - links, reinforcing R and balancing B loops), Meadows' leverage
points. Sources: references/prior-art.md and the README.

The journal is a global append-only JSONL, ~/.local/share/brainstorm/events.jsonl (override BRAINSTORM_DIR); the only
writer is `emit` here (through brainstorm.sh).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

EVENTS = {
    "session": {
        # O dono abriu uma conversa de brainstorm: uma ideia ainda aberta, antes de virar tarefa.
        "start": "started",
        # A sessão terminou: a nota de design (Decidi X porque Y) foi escrita e, se o dono concordou, vai ao backbrief.
        "finish": "finished",
    },
    "problem": {
        # O problema foi classificado no Cynefin (clear, complicated, complex, chaotic ou disorder): isso decide se a
        # resposta é regra, análise, experimento ou ação.
        "classify": "classified",
    },
    "question": {
        # Uma pergunta ao dono, uma de cada vez, pela ferramenta de perguntas do harness.
        "ask": "asked",
        # A resposta do dono, nas palavras dele.
        "answer": "answered",
    },
    "variable": {
        # Uma variável do sistema entrou no diagrama de laços causais (um nó).
        "add": "added",
    },
    "link": {
        # Uma ligação causal entre duas variáveis, com polaridade: + (mesmo sentido) ou - (sentido oposto).
        "add": "added",
    },
    "loop": {
        # Um ciclo fechado foi identificado: R (reforça, bola de neve) ou B (equilibra, busca uma meta).
        "identify": "identified",
    },
    "approach": {
        # Uma abordagem proposta, com o que ela troca (2 a 3 por vez, com recomendação).
        "propose": "proposed",
        # O dono escolheu uma abordagem: 'Decidi X porque Y'.
        "choose": "chosen",
    },
    "leverage": {
        # Pontos de alavanca de Meadows ordenados: onde agir no sistema rende mais (nível 1 a 12).
        "rank": "ranked",
    },
}

# The story: a session starts, the problem is classified, questions and answers shape the system (variables, links,
# loops), approaches are proposed and one chosen, then the session finishes.
TRANSITIONS = {
    "session.started": ["problem.classified", "question.asked"],
    "problem.classified": ["question.asked"],
    "question.asked": ["question.answered"],
    "question.answered": ["question.asked", "variable.added", "approach.proposed"],
    "variable.added": ["variable.added", "link.added"],
    "link.added": ["link.added", "loop.identified"],
    "loop.identified": ["leverage.ranked", "approach.proposed"],
    "leverage.ranked": ["approach.proposed"],
    "approach.proposed": ["approach.chosen"],
    "approach.chosen": ["session.finished"],
}

CYNEFIN = ("clear", "complicated", "complex", "chaotic", "disorder")
POLARITY = ("+", "-")
LOOP_KINDS = ("R", "B")


def _project(events: list[dict]) -> dict:
    """A session as the journal leaves it: its idea, Cynefin domain, chosen approach and the size of its system."""
    if not events:
        return {}
    state = {"id": events[-1]["session"], "idea": "", "cynefin": "", "chosen": "", "variables": 0, "links": 0,
             "loops": 0, "status": "", "updated_at": events[-1]["at"]}
    for e in events:
        v = e.get("value", {})
        kind = e["event"]
        if kind == "session.started":
            state["idea"] = v.get("text", "")
        elif kind == "problem.classified":
            state["cynefin"] = v.get("domain", "")
        elif kind == "approach.chosen":
            state["chosen"] = v.get("text", "")
        elif kind == "variable.added":
            state["variables"] += 1
        elif kind == "link.added":
            state["links"] += 1
        elif kind == "loop.identified":
            state["loops"] += 1
        state["status"] = kind.split(".")[1]
    return state


def causal_graph(events: list[dict]) -> dict:
    """The causal loop diagram of a session: {nodes: [name], edges: [{from, to, polarity}], loops: [{kind, variables}]}.
    A link names variables the session did not add yet; they become nodes too."""
    nodes: list[str] = []
    edges: list[dict] = []
    loops: list[dict] = []

    def node(name: str) -> None:
        if name not in nodes:
            nodes.append(name)

    for e in events:
        v = e.get("value", {})
        if e["event"] == "variable.added":
            node(v["name"])
        elif e["event"] == "link.added":
            node(v["from"])
            node(v["to"])
            edges.append({"from": v["from"], "to": v["to"], "polarity": v["polarity"]})
        elif e["event"] == "loop.identified":
            loops.append({"kind": v["kind"], "variables": v.get("variables", [])})
    return {"nodes": nodes, "edges": edges, "loops": loops}


class BrainstormJournal:
    """Read-only view of the Brainstorm journal for the dev-console contract."""

    def _events(self) -> list[dict]:
        return _all_events()

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        events = self._events()
        if "id" in query:
            matches = [e for e in events if e.get("session") == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for e in events:
            if e.get("session"):
                groups.setdefault(e["session"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]


# ---- CLI: the only writer of the journal (brainstorm.sh emit|sessions|graph) ----

import argparse  # noqa: E402
import sys  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime  # noqa: E402


def journal_path() -> Path:
    """The journal, read from BRAINSTORM_DIR on every call."""
    return Path(os.environ.get("BRAINSTORM_DIR", "~/.local/share/brainstorm")).expanduser() / "events.jsonl"


def _all_events() -> list[dict]:
    p = journal_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _need(value: dict, *keys: str) -> None:
    for k in keys:
        if not value.get(k):
            raise ValueError(f"value needs a non-empty `{k}`")


def validate(event: str, value: dict) -> None:
    if event == "problem.classified":
        _need(value, "domain")
        if value["domain"] not in CYNEFIN:
            raise ValueError(f"domain must be one of {CYNEFIN}")
    elif event == "variable.added":
        _need(value, "name")
    elif event == "link.added":
        _need(value, "from", "to", "polarity")
        if value["polarity"] not in POLARITY:
            raise ValueError("polarity must be '+' or '-'")
    elif event == "loop.identified":
        _need(value, "kind")
        if value["kind"] not in LOOP_KINDS:
            raise ValueError("kind must be 'R' (reinforcing) or 'B' (balancing)")
    elif event == "leverage.ranked":
        _need(value, "level")
        if not isinstance(value["level"], int) or not 1 <= value["level"] <= 12:
            raise ValueError("level must be an integer from 1 to 12 (Meadows)")
    else:
        _need(value, "text")


def emit(event: str, value: dict, session: str, actor: str = "agent") -> dict:
    valid = {f"{d}.{k}" for d, kinds in EVENTS.items() for k in kinds.values()}
    if event not in valid:
        raise ValueError(f"unknown event {event!r}; one of {sorted(valid)}")
    if not isinstance(value, dict):
        raise ValueError("value must be a JSON object")
    if not session:
        raise ValueError(f"{event} requires --session <id>")
    validate(event, value)
    row: dict[str, Any] = {"id": uuid.uuid4().hex[:12], "event": event, "session": session,
                           "at": datetime.now().astimezone().isoformat(timespec="seconds"), "actor": actor,
                           "value": value}
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def sessions(status: str | None = None) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for e in _all_events():
        if e.get("session"):
            groups.setdefault(e["session"], []).append(e)
    out = [s for g in groups.values() if (s := _project(g))]
    return [s for s in out if not status or s["status"] == status]


def graph(session: str) -> dict:
    return causal_graph([e for e in _all_events() if e.get("session") == session])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="brainstorm.py", description="Brainstorm journal: the only writer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("event")
    e.add_argument("value")
    e.add_argument("--session", required=True)
    e.add_argument("--actor", required=True)
    s = sub.add_parser("sessions")
    s.add_argument("--status")
    g = sub.add_parser("graph")
    g.add_argument("session")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            print(json.dumps(emit(a.event, json.loads(a.value), a.session, a.actor), ensure_ascii=False))
        elif a.cmd == "sessions":
            print(json.dumps(sessions(a.status), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(graph(a.session), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
