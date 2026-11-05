"""The dev-console's own domain: our development process. A Human designs a new Domain or imports one that exists;
then Domain.Updated, which links its events (Event.Updated), its widgets (Widget.Updated) and its actions (proposed,
simulated in the console, run).

The journal is DERIVED and read-only: on every read it scans <skills>/*/scripts/dev_console_project.py and parses
each with `ast` only (never imported or executed). It emits only what the code proves: the domain was imported (its
project file exists, with its home widget) and each widget updated (registered in WIDGETS). The other steps stay
outlined in the graph until the process records them.
"""
from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENTS = {
    "domain": {"design": "designed", "import": "imported", "update": "updated"},
    "event": {"update_event": "updated"},  # one event for create, update or delete of an event type: simpler at this level
    "widget": {"update_widget": "updated"},
    "tab": {"update_tab": "updated"},  # Domain is the one fixed tab; the others are the context's (create, change, delete)  # like Event: one event for create, update or delete
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
                # the event types its EVENTS registry declares, as "category.event"
                "events": [],
                # the console tabs this domain shows (Domain is always first)
                "tabs": [],
                # the widgets registered, as [{event, widget, doc}]
                "widgets": [],
                # how it entered the process: designed (new) or imported (existing code)
                "status": event.split(".")[1],
                # how many events make up this domain
                "event_count": 0,
                # when its project file last changed
                "updated_at": e["at"],
            }
        if state is None:
            continue
        if event == "tab.updated":
            state["tabs"].append(value["tab"])
        elif event == "event.updated":
            state["events"].append(value["event"])
        elif event == "widget.updated":
            state["widgets"].append({"event": value["event"], "widget": value["widget"], "doc": value.get("doc", "")})
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


def _events_registry(path: Path) -> list[tuple[str, str]]:
    """[("category.event", command)] from the EVENTS literal in a source file, read with ast."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EVENTS" for t in node.targets):
            reg = _literal(node.value) or {}
            return [(f"{c}.{ev}", cmd) for c, cmds in reg.items() if isinstance(cmds, dict) for cmd, ev in cmds.items()]
    return []


class ConsoleJournal:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else SKILLS_DIR
        self.file = Path(__file__).with_name("console_domain.jsonl")

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
        """The journal is a JSONL file next to this one (prototyping: edit it by hand). Missing: seeded from the code."""
        if not self.file.exists():
            self.file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in self._derived()))
        return [json.loads(line) for line in self.file.read_text().splitlines() if line.strip()]

    def _derived(self) -> list[dict]:
        out: list[dict] = []
        for file in sorted(self.path.glob("*/scripts/dev_console_project.py")):
            out.extend(self._events_of(file))
        return sorted(out, key=lambda e: e["at"])  # stable: keeps per-file order for equal times

    def _registry(self, file: Path, source: ast.AST | None) -> list[tuple[str, str]]:
        """The project's SOURCE (a path expression ending in a "<name>.py" string), read without running it."""
        names = [n.value for n in ast.walk(source) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and n.value.endswith(".py")] if source is not None else []
        return _events_registry(file.parent / names[-1]) if names else []

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
        # Domain.Updated: the domain's code (its EVENTS registry) as it is now; it links every Event.Updated
        for tab in ["Domain", *(_literal(assigns.get("TABS")) or [])]:  # Domain is fixed; TABS names the rest
            out.append(make("tab.updated", tab, {"tab": tab}))
        registry = self._registry(file, assigns.get("SOURCE"))
        out.append(make("domain.updated", "", {"events": len(registry)}))
        for ev, cmd in registry:
            out.append(make("event.updated", ev, {"event": ev, "command": cmd, "change": "created"}))
        widgets = assigns.get("WIDGETS")
        if isinstance(widgets, ast.Dict):
            for k, v in zip(widgets.keys, widgets.values):
                ev = _literal(k)
                if not isinstance(ev, str) or not isinstance(v, (ast.List, ast.Tuple)):
                    continue
                for fn in v.elts:
                    if isinstance(fn, ast.Name):
                        out.append(make("widget.updated", f"{ev}:{fn.id}",
                                        {"event": ev, "widget": _pascal(fn.id), "doc": funcs.get(fn.id, "")}))
        return out
