#!/usr/bin/env python3
"""tournament.py (skill choice): a tournament of options, the house way of choosing anything (logo, screen, name, text).

Each round shows 4 options with the agent's confidence (summing 100), ranked: 01 is the champion the agent picks.
The owner answers with one of three: another round (the champion against 3 new challengers), accept the champion,
or feedback (his words become a criterion for the next round). There is always a champion; the owner ends it.

  tournament.py open <slug> "<theme>" [--thread SID] [--kind logo|screen|name|text|palette]
  tournament.py round <slug> --option "<name>" <path> <pct> (x4)   round 2+ must include the current champion
  tournament.py answer <slug> another|accept|feedback ["<owner's words>"]
  tournament.py show <slug>          state as JSON: round, champion, criteria (feedback so far), last options
  tournament.py list

The journal is ~/.local/share/tournament/events.jsonl (TOURNAMENT_DIR); this file is its only writer. With --thread,
each round is drawn on the thread screen (skill thread, scripts/view.py; THREADVIEW_PY overrides): artifacts 01-04 with %, the showcase in the
dev-console, and the input turned into the round's choice.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

EVENTS = {
    "tournament": {
        # O dono (ou o agente da thread) abriu um torneio: um tema e o tipo do que vai disputar.
        "open": "opened",
        # O dono aceitou o campeão: o torneio acabou e o campeão é o resultado.
        "win": "won",
    },
    "round": {
        # Uma rodada na tela: 4 opções com a certeza do agente somando 100; a 01 é o campeão que o agente escolhe.
        "show": "shown",
        # A resposta do dono: outra rodada, aceitar, ou feedback (as palavras dele viram critério da próxima).
        "answer": "answered",
    },
}

# Few edges: open, then rounds until the owner accepts.
TRANSITIONS = {
    "tournament.opened": ["round.shown"],
    "round.shown": ["round.answered"],
    "round.answered": ["round.shown", "tournament.won"],
}
INITIAL = ["tournament.opened"]
ANSWERS = ("another", "accept", "feedback")
HERE = Path(__file__).resolve().parent
VIEWPY = os.environ.get("THREADVIEW_PY") or str(HERE.parent.parent / "thread" / "scripts" / "view.py")


def journal_path() -> Path:
    return Path(os.environ.get("TOURNAMENT_DIR", "~/.local/share/tournament")).expanduser() / "events.jsonl"


def _all_events() -> list[dict]:
    p = journal_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _project(events: list[dict]) -> dict:
    """A tournament as the journal leaves it."""
    if not events:
        return {}
    s = {"id": events[-1]["tournament"], "theme": "", "kind": "", "thread": "", "round": 0, "champion": "",
         "options": [], "criteria": [], "status": "", "updated_at": events[-1]["at"]}
    for e in events:
        v = e.get("value", {})
        k = e["event"]
        if k == "tournament.opened":
            s.update(theme=v.get("theme", ""), kind=v.get("kind", ""), thread=v.get("thread", ""))
        elif k == "round.shown":
            s["round"] = v["round"]
            s["options"] = v["options"]
            s["champion"] = v["options"][0]["name"]
        elif k == "round.answered" and v.get("answer") == "feedback":
            s["criteria"].append(v.get("text", ""))
        s["status"] = k
    return s


class TournamentJournal:
    """Read-only view of the journal for the dev-console contract."""

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        events = _all_events()
        if "id" in query:
            m = [e for e in events if e.get("tournament") == query["id"]]
            return m if query.get("history") else _project(m)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for e in events:
            groups.setdefault(e["tournament"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]


def die(msg: str) -> None:
    print(f"tournament.py: {msg}", file=sys.stderr)
    sys.exit(2)


def emit(event: str, value: dict, slug: str, actor: str = "agent") -> dict:
    valid = {f"{d}.{k}" for d, kinds in EVENTS.items() for k in kinds.values()}
    if event not in valid:
        die(f"unknown event {event}")
    state = _project([e for e in _all_events() if e.get("tournament") == slug])
    allowed = INITIAL if not state else TRANSITIONS.get(state["status"], [])
    if event not in allowed:
        die(f"{event} not allowed after {state.get('status') or 'nothing'}; next: {allowed}")
    e = {"id": uuid.uuid4().hex[:12], "event": event, "tournament": slug,
         "at": datetime.now().astimezone().isoformat(timespec="seconds"), "actor": actor, "value": value}
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e


# ---- the thread screen (view.py) ----

def _view(sid: str, *args: str, stdin: str | None = None) -> None:
    vp = VIEWPY
    if not sid or not vp:
        return
    subprocess.run([sys.executable, vp, sid, *args], input=stdin, text=True, check=False,
                   stdout=subprocess.DEVNULL)


def _view_get(sid: str) -> dict:
    vp = VIEWPY
    if not sid or not vp:
        return {}
    out = subprocess.run([sys.executable, vp, sid, "get"], text=True, capture_output=True).stdout
    return json.loads(out or "{}")


def draw_round(state: dict) -> None:
    sid = state["thread"]
    v = _view_get(sid)
    if not v and not sid:
        return
    champ = state["options"][0]["name"]
    v["artifacts"] = [{"key": f"{i:02d}", "name": o["name"], "state": "ready", "path": o["path"], "pct": o["pct"]}
                      for i, o in enumerate(state["options"], 1)]
    # Edges as fixed keys (muscle memory): the same key always walks the same edge, in every round.
    v["decision"] = {"text": f"Rodada {state['round']}. Campeão: {champ}.", "cmd": None, "options": [],
                     "keys": [{"key": "enter", "label": f"outra rodada: {champ} contra 3 novos", "send": f"torneio {state['id']}: outra rodada"},
                              {"key": "a", "label": f"aceitar {champ}", "send": f"torneio {state['id']}: aceito o campeão"},
                              {"key": "f", "label": "feedback para a próxima rodada", "send": f"torneio {state['id']} feedback: ", "type": True}]}
    v["pulse"] = f"torneio {state['id']} · rodada {state['round']} · esperando você"
    _view(sid, "put", stdin=json.dumps(v, ensure_ascii=False))
    url = _view_get(sid).get("url")
    if url and shutil.which("devc"):  # the showcase opens by itself in the dev-console, when it is installed
        subprocess.run(["devc", "open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def main(a: list[str]) -> None:
    if len(a) < 1 or a[0] in ("help", "-h", "--help"):
        print(__doc__)
        return
    cmd = a[0]
    if cmd == "list":
        for s in TournamentJournal().read():
            print(f"{s['id']}\tround {s['round']}\t{s['champion'] or '-'}\t{s['status']}\t{s['theme']}")
        return
    if len(a) < 2:
        die(f"{cmd} needs a slug")
    slug, rest = a[1], a[2:]
    state = _project([e for e in _all_events() if e.get("tournament") == slug])
    if cmd == "show":
        print(json.dumps(state, ensure_ascii=False, indent=1))
    elif cmd == "open":
        if not rest:
            die('open needs a theme: open <slug> "<theme>"')
        val = {"theme": rest[0], "kind": "", "thread": ""}
        if "--thread" in rest:
            val["thread"] = rest[rest.index("--thread") + 1]
        if "--kind" in rest:
            val["kind"] = rest[rest.index("--kind") + 1]
        emit("tournament.opened", val, slug)
        print("ok")
    elif cmd == "round":
        opts, i = [], 0
        while i < len(rest):
            if rest[i] != "--option" or i + 3 >= len(rest):
                die('use --option "<name>" <path> <pct>, four times')
            name, path, pct = rest[i + 1], rest[i + 2], rest[i + 3].rstrip("%")
            if not pct.isdigit():
                die(f"{name!r}: confidence must be a number")
            if not Path(path).expanduser().exists():
                die(f"{name!r}: no file at {path}")
            opts.append({"name": name, "path": str(Path(path).expanduser()), "pct": int(pct)})
            i += 4
        if len(opts) != 4:
            die(f"a round has 4 options (got {len(opts)})")
        if sum(o["pct"] for o in opts) != 100:
            die(f"confidence must sum 100 (got {sum(o['pct'] for o in opts)})")
        if state.get("champion") and state["champion"] not in [o["name"] for o in opts]:
            die(f"round {state['round'] + 1} must include the champion {state['champion']!r}")
        opts.sort(key=lambda o: -o["pct"])
        emit("round.shown", {"round": state.get("round", 0) + 1, "options": opts}, slug)
        state = _project([e for e in _all_events() if e.get("tournament") == slug])
        draw_round(state)
        print(f"ok · rodada {state['round']} · campeão {state['champion']}")
    elif cmd == "answer":
        if not rest or rest[0] not in ANSWERS:
            die(f"answer is one of {ANSWERS}")
        val = {"answer": rest[0], "text": rest[1] if len(rest) > 1 else ""}
        if rest[0] == "feedback" and not val["text"]:
            die("feedback needs the owner's words")
        emit("round.answered", val, slug, actor="owner")
        if rest[0] == "accept":
            emit("tournament.won", {"champion": state["champion"], "rounds": state["round"]}, slug, actor="owner")
            v = _view_get(state["thread"])
            if v:
                v["decision"] = None
                v["pulse"] = f"campeão: {state['champion']} ({state['round']} rodada{'s' if state['round'] > 1 else ''})"
                _view(state["thread"], "put", stdin=json.dumps(v, ensure_ascii=False))
        print("ok")
    else:
        die(f"unknown command {cmd}")


if __name__ == "__main__":
    main(sys.argv[1:])
