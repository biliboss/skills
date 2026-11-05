"""The dev-console's own domain: our development process. A Human designs a new Domain or imports one that exists;
then its draft, its widgets (created, updated) and its actions (proposed,
simulated in the console, run).

The journal is DERIVED and read-only: on every read it scans <skills>/*/scripts/dev_console_project.py and parses
each with `ast` only (never imported or executed). It emits only what the code proves: the domain was imported (its
project file exists, with its home widget) and each widget created (registered in WIDGETS). The other steps stay
outlined in the graph until the process records them.
"""
from __future__ import annotations

import ast
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENTS = {
    "domain": {"design": "designed", "import": "imported", "draft": "drafted"},
    "widget": {"create_widget": "created", "update_widget": "updated"},
    "action": {"propose": "proposed", "simulate": "simulated", "run": "ran"},
}

SKILLS_DIR = Path(__file__).resolve().parents[2]  # <skills>/dev-console/scripts/this_file -> <skills>


def _project(events: list[dict]) -> dict | None:
    state = None
    for e in events:
        event, value = e["event"], e["value"]
        if event in ("domain.designed", "domain.imported"):
            state = {
                # the domain's id: its slug
                "id": e["domain_id"],
                # the project's name on the console bar
                "slug": value["slug"],
                # what the project calls itself
                "name": value["name"],
                # what one item of its rail is (the aggregate root)
                "entity": value["entity"],
                # the project file that hooks it into the console
                "source": value["source"],
                # the widget the Visão tab opens with, as {event, widget}
                "home": value.get("home"),
                # the widgets registered, as [{event, widget, doc}]
                "widgets": [],
                # the names of the actions the project can run
                "actions": [],
                # how it entered the process: designed (new) or imported (existing code)
                "status": event.split(".")[1],
                # how many events make up this domain
                "event_count": 0,
                # when its project file last changed
                "updated_at": e["at"],
            }
        if state is None:
            continue
        if event == "widget.created":
            state["widgets"].append({"event": value["event"], "widget": value["widget"], "doc": value.get("doc", "")})
        elif event == "action.proposed":
            state["actions"].append(value["name"])
        state["updated_at"] = max(state["updated_at"], e["at"])
        state["event_count"] += 1
    return state


def _pascal(name: str) -> str:
    return "".join(p.capitalize() for p in name.split("_"))


def _literal(node: ast.AST | None) -> Any:
    try:
        return ast.literal_eval(node) if node is not None else None
    except (ValueError, TypeError, SyntaxError):
        return None


class ConsoleJournal:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else SKILLS_DIR

    def read(self, query: dict | None = None) -> Any:
        """{} -> every Domain; {"id"} -> one or None; {"id", "history"} -> its events;
        {"event"} -> that type everywhere; {"history"} -> every event."""
        query = query or {}
        if not isinstance(query, dict):
            raise TypeError("query must be a dict")
        events = self._events()
        if "id" in query:
            matches = [e for e in events if e["domain_id"] == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for e in events:
            groups.setdefault(e["domain_id"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]

    def _events(self) -> list[dict]:
        out: list[dict] = []
        for file in sorted(self.path.glob("*/scripts/dev_console_project.py")):
            out.extend(self._events_of(file))
        return sorted(out, key=lambda e: e["at"])  # stable: keeps per-file order for equal times

    def _events_of(self, file: Path) -> list[dict]:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return []
        at = datetime.fromtimestamp(file.stat().st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        assigns: dict[str, ast.AST] = {}
        funcs: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                assigns[node.targets[0].id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                assigns[node.target.id] = node.value
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs[node.name] = (ast.get_docstring(node) or "").strip().splitlines()[0] if ast.get_docstring(node) else ""
        folder = file.parent.parent.name
        slug = _literal(assigns.get("SLUG")) or folder
        name = _literal(assigns.get("NAME")) or slug
        entity = _literal(assigns.get("ENTITY")) or ""
        source = str(file.relative_to(self.path))

        def make(event: str, key: str, value: dict) -> dict:
            eid = hashlib.sha1(f"{slug}{event}{key}".encode()).hexdigest()
            return {"id": eid, "event": event, "at": at, "actor": "código", "domain_id": slug, "value": value}

        home = _literal(assigns.get("HOME"))
        home = {"event": home[0], "widget": home[1]} if isinstance(home, (tuple, list)) and len(home) == 2 else None
        out = [make("domain.imported", "", {"name": name, "slug": slug, "entity": entity, "source": source, "home": home})]
        widgets = assigns.get("WIDGETS")
        if isinstance(widgets, ast.Dict):
            for k, v in zip(widgets.keys, widgets.values):
                ev = _literal(k)
                if not isinstance(ev, str) or not isinstance(v, (ast.List, ast.Tuple)):
                    continue
                for fn in v.elts:
                    if isinstance(fn, ast.Name):
                        out.append(make("widget.created", f"{ev}:{fn.id}",
                                        {"event": ev, "widget": _pascal(fn.id), "doc": funcs.get(fn.id, "")}))
        return out
