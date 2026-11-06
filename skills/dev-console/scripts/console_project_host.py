#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-fasthtml>=0.14", "monsterui>=1.0.48"]
# ///
"""The dev-console's project host: the Python half of the console that cannot be TypeScript.

dev-console.ts (Hono) is the whole web server. But the PROJECT CONTRACT (references/project-contract.md) is Python:
a project is a `dev_console_project.py` that the console imports; its SOURCE is read with `ast`, its widgets are
functions that return FastHTML components, and its journal/ACTIONS are Python. Seventeen such files live in other
skills and repos, so the server cannot import them. This script is the thin bridge: ONE long-lived process that loads
every project and answers the server over stdin/stdout, one JSON object per line:

    request  {"id": 7, "op": "widget", ...args}
    response {"id": 7, "ok": true, "data": ...}   |   {"id": 7, "ok": false, "error": "..."}

It writes nothing the server does not ask for, serves no HTTP and has no UI. A project reload is a new process (the
server restarts it when a project folder changes), so there is no module purging here.
Run (by the server, never by hand):  uv run --script console_project_host.py --project <a> [--project <b>]
Ops: ready-info (sent first, unsolicited), page, state, default_entity, rail, model, widget, widget_list, action,
money, entities. See `OPS` at the bottom.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from contextvars import ContextVar

from fasthtml.common import H2, Button, Div, Iframe, Li, NotStr, P, Span, Ul, to_xml

PLAYGROUND_SLUG = "playground"
PLAYGROUND_COST_CENTER = os.environ.get("DEV_CONSOLE_PLAYGROUND_COST_CENTER", "biliboss-skills")
PROJECT_PATHS: dict = {}  # project file -> the folders its import added to sys.path


def load_project(path: str):
    """Import the project file (it may import its own code from its folder)."""
    folder = Path(path).resolve().parent
    spec = importlib.util.spec_from_file_location("dev_console_project", path)
    mod = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    sys.path.insert(0, str(folder))
    spec.loader.exec_module(mod)
    PROJECT_PATHS[str(path)] = [Path(x) for x in sys.path if x not in before]  # what this project put on sys.path
    return mod


# One domain per project file: /domain/<slug>. A request sets the current domain (use(slug)); PROJECT, journal and
# SOURCE below always read the current one.
DOMAINS: dict = {}
ORIGIN: dict = {}  # slug -> "--project" | "registry"; GET /api/domains says it


def load_domains(paths: list[str], flagged: set[str]) -> None:
    for path in paths:
        mod = load_project(path)
        slug = getattr(mod, "SLUG", None) or Path(path).resolve().parent.parent.name
        mod.SLUG, mod.BASE = slug, f"/domain/{slug}"  # BASE: the domain's URL prefix (actions build links with it)
        DOMAINS[slug] = mod
        ORIGIN[slug] = "--project" if path in flagged else "registry"


CURRENT: ContextVar = ContextVar("domain", default=None)


def use(slug: str):
    """Make <slug> the current domain for this request; None if there is no such domain."""
    mod = DOMAINS.get(slug)
    if mod is not None:
        CURRENT.set(mod)
    return mod


class _Live:
    """A name that always reads from the current domain (PROJECT, journal, SOURCE)."""

    def __init__(self, get):
        object.__setattr__(self, "_get", get)

    def __getattr__(self, name):
        return getattr(self._get(), name)


PROJECT = _Live(CURRENT.get)
journal = _Live(lambda: CURRENT.get().journal)
SOURCE = _Live(lambda: Path(CURRENT.get().SOURCE))


def derive(events: dict, initial: list[str] | None = None, hub: str | None = None,
           transitions: dict | None = None) -> dict:
    """Everything the screen shows comes from EVENTS ({category: {command: event}}, ordered):
    the categories and their events, the commands, and the graph edges (created opens every other
    category; inside a category each event follows the previous one)."""
    lifecycle = {c: list(dict.fromkeys(cmds.values())) for c, cmds in events.items()}
    commands: dict[str, str] = {}  # several commands may record one event (upscore | downscore -> Style.Scored)
    for c, cmds in events.items():
        for cmd, ev in cmds.items():
            key = f"{c}.{ev}"
            commands[key] = f"{commands[key]} | {cmd}" if key in commands else cmd
    root = next(f"{c}.{evs[0]}" for c, evs in lifecycle.items())
    # INITIAL (optional, in the project file): the events the Human may start with; the first is the root, the others
    # are alternative starts that lead to the same next step (e.g. Domain.Designed or Domain.Imported).
    initial = [e for e in (initial or [root]) if e in commands] or [root]
    root = initial[0]
    nxt: dict[str, list[str]] = {}
    for c, evs in lifecycle.items():
        chain = [f"{c}.{ev}" for ev in evs if f"{c}.{ev}" not in initial[1:]]
        if chain[0] != root:  # every other category opens from the root, or from the HUB when the project names one
            nxt.setdefault(hub if hub in commands else root, []).append(chain[0])
        for x, y in zip(chain, chain[1:]):
            nxt.setdefault(x, []).append(y)
    for alt in initial[1:]:  # an alternative start joins the root's own next step
        nxt[alt] = [n for n in nxt.get(root, []) if n.split(".")[0] == root.split(".")[0]][:1]
    # TRANSITIONS (optional, UML statechart term): {"cat.event": ["cat.event", ...]} replaces the derived edges when the
    # process branches or loops (a teach-back that goes back to the explanation); the Human still opens INITIAL.
    # A target may name the command of that edge ({"style.scored": "downscore"}) when one event has several commands.
    edge_cmd: dict[str, str] = {}
    if transitions:
        nxt = {}
        for s, ts in transitions.items():
            if s not in commands:
                continue
            nxt[s] = [t for t in ts if t in commands]
            if isinstance(ts, dict):
                edge_cmd.update({f"{s}>{t}": cmd for t, cmd in ts.items() if t in commands and cmd})
    return {"lifecycle": lifecycle, "commands": commands, "next": nxt, "root": root, "initial": initial,
            "hub": hub if hub in commands else None, "edge_cmd": edge_cmd}


def value_objects() -> list[dict]:
    """The domain's value objects, read live from SOURCE with ast: every frozen dataclass (equal by value, no identity),
    with its docstring, fields and line; VALUES = {"cat.event": "ClassName"} in SOURCE says which event carries which."""
    import ast

    tree = ast.parse(SOURCE.read_text())
    carried: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VALUES" for t in node.targets):
            try:
                carried = {v: k for k, v in ast.literal_eval(node.value).items()}
            except ValueError:
                pass
    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        frozen = any(isinstance(d, ast.Call) and "dataclass" in ast.unparse(d.func)
                     and any(k.arg == "frozen" and ast.unparse(k.value) == "True" for k in d.keywords)
                     for d in node.decorator_list)
        enum = any("Enum" in ast.unparse(base) for base in node.bases)  # typed values: an enum is a value object too
        if enum:
            members = [st.value.value for st in node.body if isinstance(st, ast.Assign) and isinstance(st.value, ast.Constant)]
            out.append({"name": node.name, "line": node.lineno, "doc": (ast.get_docstring(node) or "").split("\n")[0],
                        "fields": [], "members": members, "event": carried.get(node.name)})
            continue
        if not frozen:
            continue
        fields = [(st.target.id, ast.unparse(st.annotation), st.lineno) for st in node.body
                  if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and "ClassVar" not in ast.unparse(st.annotation)]
        out.append({"name": node.name, "line": node.lineno, "doc": (ast.get_docstring(node) or "").split("\n")[0],
                    "fields": fields, "event": carried.get(node.name)})
    return out


def descriptions() -> dict:
    """What each event means, for a human: the code comment of its command in EVENTS (the comment lines right above
    it, or the one at the end of its line), read live from SOURCE. The code is the only source: no other place."""
    import ast

    out: dict[str, str] = {}
    lines = SOURCE.read_text().splitlines()
    for node in ast.parse(SOURCE.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EVENTS" for t in node.targets) \
                and isinstance(node.value, ast.Dict):
            for ck, cv in zip(node.value.keys, node.value.values):
                if isinstance(cv, ast.Dict):
                    for k, v in zip(cv.keys, cv.values):
                        above, i = [], k.lineno - 2
                        while i >= 0 and lines[i].strip().startswith("#"):
                            above.insert(0, lines[i].strip().lstrip("#").strip())
                            i -= 1
                        line = lines[v.end_lineno - 1]
                        text = " ".join(above) or (line.split("#", 1)[1].strip() if "#" in line else "")
                        if text:
                            out[f"{ast.literal_eval(ck)}.{ast.literal_eval(v)}"] = text
    return out


def live_events() -> dict:
    """EVENTS as written in the project SOURCE right now (ast.literal_eval of the assignment)."""
    import ast

    for node in ast.parse(SOURCE.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EVENTS" for t in node.targets):
            return ast.literal_eval(node.value)
    return {}


def real_model() -> dict:
    """The public surface of the project SOURCE, signatures only, read with the stdlib ast parser.

    EVENTS as written; each class with its methods as `def name(args) -> ret` and the first
    line of the docstring as a comment. One entry per line, with its real line number.
    """
    import ast

    tree = ast.parse(SOURCE.read_text())
    lines: list[dict] = []
    props: list[str] = []

    def sig(f: ast.FunctionDef | ast.AsyncFunctionDef, indent: str) -> None:
        for d in f.decorator_list:
            lines.append({"line": d.lineno, "code": f"{indent}@{ast.unparse(d)}"})
        ret = f" -> {ast.unparse(f.returns)}" if f.returns else ""
        doc = (ast.get_docstring(f) or "").strip().splitlines()
        note = f"  # {doc[0]}" if doc else ""
        lines.append({"line": f.lineno, "code": f"{indent}def {f.name}({ast.unparse(f.args)}){ret}: ...{note}"})

    # The entity may have no class in the code: it is the dict that the PROJECTOR folds from the events.
    # Its properties are the keys of that dict literal (`state = {...}`), with the expression that fills each one.
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == PROJECT.PROJECTOR:
            for a in ast.walk(node):
                if (isinstance(a, ast.Assign) and isinstance(a.value, ast.Dict)
                        and any(isinstance(t, ast.Name) and t.id == "state" for t in a.targets)):
                    lines.append({"line": a.lineno, "code": f"class {PROJECT.ENTITY}:  # projected by {PROJECT.PROJECTOR}"})
                    src = SOURCE.read_text().splitlines()
                    for k, v in zip(a.value.keys, a.value.values):
                        props.append(ast.literal_eval(k))
                        # ast drops comments: take the comment line right above the key, if any
                        above = src[k.lineno - 2].strip() if k.lineno >= 2 else ""
                        note = f"  {above}" if above.startswith("#") else ""
                        lines.append({"line": k.lineno, "code": f"    {ast.literal_eval(k)} = {ast.unparse(v)}{note}"})
                    # Commands by category, straight from EVENTS: each command records one event.
                    model = derive(live_events(), getattr(PROJECT, "INITIAL", None), getattr(PROJECT, "HUB", None),
                         getattr(PROJECT, "TRANSITIONS", None))
                    cat_line = {}  # each command is written in EVENTS, on its category's line
                    for top in tree.body:
                        if isinstance(top, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EVENTS" for t in top.targets) \
                                and isinstance(top.value, ast.Dict):
                            cat_line = {ast.literal_eval(k): k.lineno for k in top.value.keys}
                    for cat, cmds in live_events().items():
                        lines.append({"line": None, "code": ""})
                        lines.append({"line": None, "code": f"    # {cat}"})
                        for cmd, ev in cmds.items():
                            if f"{cat}.{ev}" in model["initial"]:
                                lines.append({"line": None, "code": "    @staticmethod"})
                            lines.append({"line": cat_line.get(cat), "code": f"    def {cmd}(value): ...  # -> {cat}.{ev}"})
                    lines.append({"line": None, "code": ""})
                    break

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EVENTS" for t in node.targets):
            for i, text in enumerate(ast.get_source_segment(SOURCE.read_text(), node).splitlines()):
                lines.append({"line": node.lineno + i, "code": text})
            lines.append({"line": None, "code": ""})
        elif isinstance(node, ast.ClassDef):
            bases = f"({', '.join(ast.unparse(x) for x in node.bases)})" if node.bases else ""
            lines.append({"line": node.lineno, "code": f"class {node.name}{bases}:"})
            for f in node.body:
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig(f, "    ")
            lines.append({"line": None, "code": ""})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig(node, "")
    return {"file": SOURCE.name, "mtime": SOURCE.stat().st_mtime, "lines": lines, "props": props,
            "coverage": W.coverage(live_events()), "descriptions": descriptions(), "value_objects": value_objects(),
            "layout": getattr(PROJECT, "LAYOUT", None) or "branch",
            "stages": dict(getattr(PROJECT, "STAGES", None) or {}), "stage_order": list(getattr(PROJECT, "STAGE_ORDER", None) or []),
            "stage_labels": dict(getattr(PROJECT, "STAGE_LABELS", None) or {}), **derive(live_events(), getattr(PROJECT, "INITIAL", None), getattr(PROJECT, "HUB", None),
                         getattr(PROJECT, "TRANSITIONS", None))}


# --- the domain draft: dummy code the user edits ------------------------------------------------------------------
# <SOURCE stem>_draft.py next to SOURCE (or PROJECT.DOMAIN_DRAFT). Generated once from EVENTS and the projector when it
# does not exist, never overwritten: classes with fields and command stubs, no implementation. The base class is the
# DDD stereotype (AggregateRoot, Entity, ValueObject, DomainEvent).
DDD_BASES = ("AggregateRoot", "Entity", "ValueObject", "DomainEvent")


def draft_path(mod=None) -> Path:
    mod = mod or CURRENT.get()
    src = Path(mod.SOURCE)
    return Path(getattr(mod, "DOMAIN_DRAFT", None) or src.with_name(f"{src.stem}_draft.py"))


def _pascal(w: str) -> str:
    return "".join(x.capitalize() for x in w.split("_"))


def write_draft(mod) -> None:
    """Write the dummy draft for a domain if it does not exist (the user's edits always win)."""
    path = draft_path(mod)
    if path.exists():
        return
    token = CURRENT.set(mod)
    try:
        events, props = live_events(), real_model()["props"]
    finally:
        CURRENT.reset(token)
    if not events:
        return
    ents = getattr(mod, "ENTITIES", {})
    cats = list(events)
    name = lambda c: ents.get(c) or _pascal(c)  # noqa: E731
    out = [f'"""{mod.NAME}: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.',
           "",
           "Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.",
           '"""', "from __future__ import annotations", "", "",
           *[f"class {b}: ...\n\n" for b in DDD_BASES]]
    root = cats[0]
    out += [f"class {name(root)}(AggregateRoot):", f'    """{name(root)}: the aggregate root of {mod.NAME}."""', ""]
    rel = {f"{c}s": name(c) for c in cats[1:]}  # the root holds a list of each other category's entity
    out += [f"    {p}: list[{rel[p]}]" if p in rel else f"    {p}: Any" for p in props]
    out += [f"    {p}: list[{e}]" for p, e in rel.items() if p not in props]
    out += [""] + [f"    def {cmd}(self) -> {_pascal(root)}{_pascal(ev)}: ..." for cmd, ev in events[root].items()]
    for c in cats[1:]:
        out += ["", "", f"class {name(c)}(Entity):", f'    """{name(c)}: held by {name(root)}."""', ""]
        out += [f"    def {cmd}(self) -> {_pascal(c)}{_pascal(ev)}: ..." for cmd, ev in events[c].items()]
    path.write_text("\n".join(out).replace("from __future__ import annotations",
                    "from __future__ import annotations\n\nfrom typing import Any") + "\n")


# --- widgets: the contract ------------------------------------------------------------------------------
# A project maps events to views: WIDGETS = {"category.event": [fn, ...]}, fn(ctx: EventContext) -> component.
# The function name is the widget's name on screen (tension_list -> TensionList); its docstring's first
# line is the description. Every event also gets Observability. Widgets render a real event only.

@dataclass(frozen=True)
class EventContext:
    event: str                  # "category.event"
    focus: dict | None          # the real event rendered (default: the first of this type in the journal)
    entity_id: str              # the focus event's entity
    events: list[dict]          # that entity's events of this type, oldest first
    state: dict                 # the projected entity
    journal_events: list[dict]  # this type across the whole journal
    entities: list[dict]        # every projected entity, with "title"
    history: tuple = ()         # every event of the entity, oldest first
    mode: str = "real"          # "real" or "sim": in sim, actions only play what would happen
    domain: str = ""            # the domain the screen is about (the Task Results tab filters by it)

    def expected(self, spec: dict | None):
        """Render what a proposal expects at the end (see render_expected)."""
        return render_expected(spec)

    def of(self, event: str) -> "EventContext":
        """The same entity seen through another event: lets one widget embed another (composition)."""
        from dataclasses import replace

        evs = [e for e in self.history if e["event"] == event]
        return replace(self, event=event, events=evs, focus=evs[0] if evs else None,
                       journal_events=journal.read({"event": event}))


# --- expected output: stock components a proposal can use to show what it will deliver -----------------
# spec = {"kind": "report", "data": "<markdown>"} | {"kind": "list", "data": ["…"]}
#      | {"kind": "table", "data": {"columns": [...], "rows": [[...]]}} | {"kind": "widget", "name": "...", "data": {...}}
# A "widget" kind is a dummy view the proposal brings (PROJECT.EXPECTED_WIDGETS[name](data)): cheap to propose,
# real only when the work is done. Every expected block says it is an example.

def render_expected(spec: dict | None):
    if not spec:
        return None
    kind, data = spec.get("kind"), spec.get("data")
    if kind == "report":
        from monsterui.all import render_md
        body = Div(NotStr(render_md(data or "")), cls="font-sans text-sm leading-6 [&_p]:my-1 [&_strong]:font-semibold")
    elif kind == "list":
        body = Ul(*[Li(x, cls="py-0.5 font-sans text-sm") for x in data or []], cls="list-disc pl-5")
    elif kind == "table":
        cols, rows = (data or {}).get("columns", []), (data or {}).get("rows", [])
        body = NotStr("<table class='w-full text-left'><thead><tr>"
                      + "".join(f"<th class='py-1 pr-3 font-medium text-neutral-500'>{c}</th>" for c in cols)
                      + "</tr></thead><tbody>"
                      + "".join("<tr class='border-t border-neutral-200'>"
                                + "".join(f"<td class='py-1 pr-3 font-sans'>{v}</td>" for v in r) + "</tr>" for r in rows)
                      + "</tbody></table>")
    elif kind == "widget":
        fn = getattr(PROJECT, "EXPECTED_WIDGETS", {}).get(spec.get("name", ""))
        body = fn(data or {}) if fn else _empty(f"widget {spec.get('name')} ainda não existe no projeto")
    else:
        body = _empty(f"tipo de saída {kind!r} desconhecido")
    label = spec.get("title") or {"report": "relatório", "list": "lista", "table": "tabela"}.get(kind, spec.get("name", ""))
    return Div(
        Div(Span(spec.get("heading", "Esperado no final"), cls="font-semibold text-neutral-600"),
            Span(label if spec.get("heading") else f"{label} · exemplo", cls="text-neutral-400"), cls="flex justify-between gap-3"),
        Div(body, cls="mt-2 text-neutral-700"),
        cls="mt-3 rounded border border-dashed border-neutral-300 px-3 py-2.5",
    )


def render_widget_list(slug: str, event: str, eid: str | None = None):
    """The real WidgetList of <event> in domain <slug>: the same component the right menu shows. Widgets compose it."""
    mod = DOMAINS.get(slug)
    if mod is None:
        return _empty(f"domínio {slug} não existe")
    token = CURRENT.set(mod)
    try:
        return render_list(_ctx(slug, event, eid))
    finally:
        CURRENT.reset(token)


def render_screens(steps: list[dict], title: str = "", width: int = 390, height: int = 844, scale: float = 0.62):
    """The product's real screens, composed (never redrawn): each step {name, url, event?, note?} is an iframe of the
    product's own URL (a Storybook story, a prototype, the app) in a phone frame, stepped with ← → and the dots; the
    step's event (the one the screen leads to) shows beside its name. A widget of an event passes the steps around it."""
    if not steps:
        return _empty("nenhuma tela")
    data = json.dumps([{k: st.get(k) for k in ("name", "url", "event", "note")} for st in steps], ensure_ascii=False)
    w, h = round(width * scale), round(height * scale)
    go = ("(function(b,d){var r=b.closest('[data-screens]'),S=JSON.parse(r.dataset.screens),"
          "i=Math.max(0,Math.min(S.length-1,(d==null?+b.dataset.i:+r.dataset.i+d)));r.dataset.i=i;var s=S[i];"
          "r.querySelector('iframe').src=s.url;r.querySelector('[data-n]').textContent=(i+1)+'/'+S.length+' · '+s.name;"
          "r.querySelector('[data-e]').textContent=s.event||'';r.querySelector('[data-note]').textContent=s.note||'';"
          "r.querySelectorAll('[data-dot]').forEach(function(x,j){x.style.opacity=j===i?1:.35});})")
    btn = "px-2 h-7 rounded border border-neutral-300 text-neutral-600 hover:bg-neutral-100"
    first = steps[0]
    return Div(
        H2(title, cls="mb-3 font-sans text-base font-semibold text-neutral-900") if title else "",
        Div(Button("←", type="button", cls=btn, onclick=f"{go}(this,-1)"),
            Span(f"1/{len(steps)} · {first.get('name', '')}", data_n="1", cls="flex-1 min-w-0 truncate text-neutral-700"),
            Span(first.get("event") or "", data_e="1", cls="shrink-0 font-mono text-xs text-amber-600"),
            Button("→", type="button", cls=btn, onclick=f"{go}(this,1)"), cls="flex items-center gap-2"),
        Div(Iframe(src=first.get("url", ""), style=f"width:{width}px;height:{height}px;border:0;transform:scale({scale});transform-origin:0 0"),
            style=f"width:{w}px;height:{h}px;overflow:hidden",
            cls="mt-3"),  # the product draws its own device frame (a Storybook story does)
        Div(*[Span(cls="inline-block w-2 h-2 rounded-full bg-neutral-500 cursor-pointer", data_dot="1", data_i=str(i),
                   style=f"opacity:{1 if i == 0 else .35}", onclick=f"{go}(this)") for i in range(len(steps))],
            cls="mt-2 flex gap-1.5"),
        P(first.get("note") or "", data_note="1", cls="mt-2 text-sm text-neutral-500"),
        data_screens=data, data_i="0",
    )


for _mod in DOMAINS.values():
    _mod.render_screens = render_screens  # the product's real screens, composed (an iframe of its own URL)
    _mod.render_expected = render_expected  # actions may render an expected spec too
    _mod.render_widget_list = render_widget_list  # WidgetList, composable: the right menu's own list


def widget_name(fn) -> str:
    return "".join(w.capitalize() for w in fn.__name__.split("_"))


def _when(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")


def _empty(text: str):
    return P(text, cls="text-neutral-400")


def observability(ctx: EventContext):
    """Count here and in the journal, first and last, who, and a time strip."""
    js = ctx.journal_events
    if not js:
        return _empty("Nenhum evento deste tipo no diário ainda.")
    times = [datetime.fromisoformat(e["at"].replace("Z", "+00:00")).timestamp() for e in js]
    lo, span = min(times), (max(times) - min(times)) or 1
    mine = {e["id"] for e in ctx.events}
    dots = "".join(f'<circle cx="{6 + 288 * (t - lo) / span:.1f}" cy="10" r="3.4" stroke="currentColor" '
                   f'fill="{"currentColor" if e["id"] in mine else "none"}"/>' for t, e in zip(times, js))
    return Div(
        Div(Div(P(str(len(ctx.events)), cls="text-2xl font-semibold tabular-nums"), P("nesta entidade", cls="text-neutral-400")),
            Div(P(str(len(js)), cls="text-2xl font-semibold tabular-nums"), P("no diário", cls="text-neutral-400")),
            cls="grid grid-cols-2 gap-4"),
        NotStr(f'<svg viewBox="0 0 300 20" class="mt-3 w-full h-5 text-neutral-700">'
               f'<line x1="0" y1="10" x2="300" y2="10" stroke="currentColor" stroke-opacity=".2"/>{dots}</svg>'),
        Div(Span(_when(js[0]["at"])), Span(_when(js[-1]["at"])), cls="flex justify-between text-neutral-400"),
        P("quem: " + ", ".join(sorted({e["actor"] for e in js})), cls="mt-1 text-neutral-500"),
    )


def _widgets(event: str) -> list:
    return list(getattr(PROJECT, "WIDGETS", {}).get(event, []))


def available(event: str) -> list[tuple[str, str]]:
    doc = lambda fn: (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""  # noqa: E731
    return [(widget_name(fn), doc(fn)) for fn in _widgets(event)]  # Observability is the right menu's last tab, not a widget


def render_list(ctx: EventContext):
    f = ctx.focus
    head = (P(f"dados reais: {f['id'][:8]} · {_when(f['at'])} · {PROJECT.ENTITY.lower()} {f[entity_key()][:8]}",
              cls="px-4 pt-3 text-neutral-400") if f else P(f"nenhum {ctx.event} no diário ainda", cls="px-4 pt-3 text-neutral-400"))
    # A nested tree: a widget that names its visible parts (fn.parts = [child, ...]) shows them under it, indented with a
    # guide line; a part shown under a parent is not repeated at the top. Only the parts someone asked to see are named.
    fns = {widget_name(f): f for f in _widgets(ctx.event)}
    docs = dict(available(ctx.event))
    kids = {n: [widget_name(k) for k in getattr(f, "parts", []) if widget_name(k) in fns] for n, f in fns.items()}
    nested = {k for ks in kids.values() for k in ks}

    def row(name: str, depth: int, seen: frozenset):
        here = Li(Div(Div(*[Span(cls="w-4 shrink-0 self-stretch border-l border-neutral-300 ml-1")
                              for _ in range(depth)],
                          Div(P(name, cls="font-semibold text-neutral-800"),
                              P(docs.get(name) or "todo evento", cls="text-neutral-400"), cls="min-w-0"),
                          cls="flex min-w-0 gap-2"),
                      cls="min-w-0"),
           NotStr(f'<button class="w-open shrink-0 px-2 h-7 rounded border border-neutral-300 '
                  f'text-neutral-700 hover:bg-neutral-100" data-w="{name}" tabindex="-1">abrir</button>'),
           # the whole row opens the widget (click, Enter or Space): a bigger target, and a keyboard stop (WCAG 2.1.1, 2.5.5)
           # no role="button": Pico/MonsterUI paints [role=button] as a blue centred button; the row keeps the list look
           tabindex="0", data_w=name, data_ev=ctx.event, data_base=PROJECT.BASE, aria_haspopup="dialog", aria_label=f"abrir {name}",
           aria_level=str(depth + 1),
           cls="w-row flex items-center justify-between gap-3 px-4 py-3 cursor-pointer border-b border-neutral-200 "
               "hover:bg-neutral-100 focus:outline-none "
               "focus-visible:bg-neutral-100")
        out = [here]
        for k in kids.get(name, []):
            if k not in seen:  # a part that composes its own parent would loop
                out += row(k, depth + 1, seen | {k})
        return out

    items = []
    for name, _ in available(ctx.event):
        if name not in nested:
            items += row(name, 0, frozenset({name}))
    return Div(head, Ul(*items, role="tree" if nested else None))


def render_one(ctx: EventContext, name: str):
    fn = next((f for f in _widgets(ctx.event) if widget_name(f) == name), None)
    if fn is not None and getattr(fn, "fake", False):  # the design step: fake data before the connection
        return fn(ctx)
    if ctx.focus is None and name != "Observability":
        return _empty(f"Nenhum evento {ctx.event} no diário ainda: o widget só renderiza dados reais.")
    if name == "Observability":
        return observability(ctx)
    return fn(ctx) if fn else _empty(f"Widget {name} não está registrado para {ctx.event}.")


def coverage(events_by_category: dict) -> dict[str, list[str]]:
    return {f"{c}.{ev}": [widget_name(f) for f in _widgets(f"{c}.{ev}")]
            for c, cmds in events_by_category.items() for ev in cmds.values()}


W = SimpleNamespace(EventContext=EventContext, render_list=render_list, render_one=render_one, coverage=coverage)

def entity_key() -> str:
    """The journal field that names the entity, in the current domain."""
    return getattr(PROJECT, "ENTITY_KEY", "tension_id")


def _ctx(tid: str, event: str, eid: str | None = None, mode: str = "real", domain: str = ""):
    """Context for a real event: ?e=<event id>, else the first event of this type in the journal.
    Its entity (not the one on screen) is what the widget renders."""
    of_type = journal.read({"event": event})
    focus = next((e for e in of_type if e["id"] == eid), None) or (of_type[0] if of_type else None)
    tid = (focus.get(entity_key()) or tid) if focus else tid  # an event of no entity (worth) keeps the page one
    entities = [{**t, "title": PROJECT.title_of(journal.read({"id": t["id"], "history": True}), t)} for t in journal.read()]
    return W.EventContext(
        event=event, focus=focus, entity_id=tid,
        events=[e for e in journal.read({"id": tid, "history": True}) if e["event"] == event],
        state=journal.read({"id": tid}) or {}, journal_events=of_type, entities=entities,
        history=tuple(journal.read({"id": tid, "history": True})), mode=mode, domain=domain,
    )


for _mod in DOMAINS.values():
    pass  # (the render_* hooks are attached in main(), after the projects are loaded)


# --- the widgets catalogue: every registered widget of the loaded projects, for the server's SQLite `widgets` table ----
def collect() -> list[dict]:
    """Every registered widget of the loaded projects, the way the console names them (the server mirrors it in SQLite)."""
    import hashlib
    import inspect

    out, seen = [], set()
    for slug, mod in DOMAINS.items():
        roles: dict = {}
        for module, (ev, wn) in (getattr(mod, "MODULE_WIDGETS", None) or {}).items():
            roles.setdefault((ev, wn), []).append(f"module:{module}")
        for part, wn in (getattr(mod, "ENTITY_PARTS", None) or {}).items():
            roles.setdefault(("*", wn), []).append(f"entity_part:{part}")
        home, parts_done = getattr(mod, "HOME", None), set()

        def add(kind, ev, fn, pos):
            try:
                code, file, line = inspect.getsource(fn), inspect.getsourcefile(fn), inspect.getsourcelines(fn)[1]
            except (TypeError, OSError):
                code, file, line = None, None, None
            wn = widget_name(fn) if hasattr(fn, "__name__") else repr(fn)
            r = list(roles.get((ev, wn), []))
            if ("*", wn) in roles and wn not in parts_done:  # a sidebar part: only on the first event it appears
                r += roles[("*", wn)]
                parts_done.add(wn)
            if home is not None and (home == wn or getattr(home, "__name__", None) == getattr(fn, "__name__", "")):
                r.append("home")
            wid = f"{slug}/{ev}/{wn}"
            if wid in seen:
                wid += f"#{pos}"
            seen.add(wid)
            out.append({"id": wid, "domain": slug, "event": ev, "name": wn, "kind": kind, "position": pos,
                        "function": getattr(fn, "__name__", None), "module": getattr(fn, "__module__", None), "file": file,
                        "line": line, "fake": int(bool(getattr(fn, "fake", False))), "roles": json.dumps(r), "code": code,
                        "code_sha256": hashlib.sha256(code.encode()).hexdigest() if code else None,
                        "project": getattr(mod, "__file__", None)})

        for ev, fns in (getattr(mod, "WIDGETS", None) or {}).items():
            for i, fn in enumerate(fns if isinstance(fns, (list, tuple)) else [fns]):
                add("widget", ev, fn, i)
        for i, (_n, fn) in enumerate((getattr(mod, "EXPECTED_WIDGETS", None) or {}).items()):
            add("expected", "expected", fn, i)
    return out


def watch_dirs() -> list[str]:
    """The folders the server must watch: each project's, what loading them added to sys.path, the folders of the
    non-library modules they loaded, and each project's `WATCH` list (paths relative to its own folder)."""
    import sysconfig

    skip = tuple(str(Path(p).resolve()) for p in {sysconfig.get_paths()["stdlib"], sysconfig.get_paths()["purelib"],
                                                 sysconfig.get_paths()["platlib"], sys.prefix, sys.base_prefix})

    def foreign(p: Path) -> bool:
        s = str(p.resolve())
        return "site-packages" in s or any(s == k or s.startswith(k + "/") for k in skip)

    out = {Path(m.__file__).resolve().parent for m in DOMAINS.values()}
    out |= {Path(p).resolve() for ds in PROJECT_PATHS.values() for p in ds if Path(p).is_dir() and not foreign(Path(p))}
    out |= {(Path(m.__file__).parent / w).resolve() for m in DOMAINS.values() for w in getattr(m, "WATCH", ())}
    for mod in list(sys.modules.values()):
        file = getattr(mod, "__file__", None)
        if file and Path(file).exists() and not foreign(Path(file)) and ".hermes" not in Path(file).parts[-6:-1]:
            out.add(Path(file).resolve().parent)
    return sorted(str(d) for d in out if d.is_dir() and d != Path.home() and d != Path("/"))


# --- the money bar: the Costs domain's journal is the only storage (cost-track's costs.py is its only writer) ----------
def _load_costs():
    """cost-track's costs.py, next to this skill in the skills folder; None (no bar) when it is not there."""
    path = Path(__file__).resolve().parent.parent.parent / "cost-track" / "scripts" / "costs.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("dev_console_costs", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


C = _load_costs()
# The clock is written by cost-track's `costs.sh tmux-focus` (the tmux session he is attached to), not by this window.
# DEVC_CLOCK_DRIVER=1 brings the window back as a second writer (off by default).
CLOCK_DRIVER = os.environ.get("DEVC_CLOCK_DRIVER", "") == "1"
ENDED_BY = ("pause", "domain_change", "hidden", "idle", "close")
STALE_SECONDS = 45  # the page pings every ~10 s while running; silence this long means the page is gone


def _now():
    return datetime.now().astimezone()


def _center_of(slug: str) -> str | None:
    if slug == PLAYGROUND_SLUG and slug not in DOMAINS:  # the Playground has no domain: its center is this console's config
        return C.center_of(slug, PLAYGROUND_COST_CENTER) if C else None
    return C.center_of(slug, getattr(DOMAINS[slug], "COST_CENTER", None)) if C else None


def _close_run(ended_by: str, now=None, trim: float = 0.0):
    """End the running stretch: one time_entry.stopped (seconds, the rate it started with, the cost)."""
    from datetime import timedelta

    run = C.running() if C else None
    if not run:
        return None
    started = datetime.fromisoformat(run["started_at"])
    end = max((now or _now()) - timedelta(seconds=max(trim, 0)), started)
    seconds = round((end - started).total_seconds())
    cost = round(seconds * run["rate_hour"] / 3600, 2)
    ev = C.emit("time_entry.stopped", {"text": C.stopped_text(run["center"], run["domain"], seconds, cost), "domain": run["domain"],
                                       "seconds": seconds, "rate_hour": run["rate_hour"], "cost": cost,
                                       "ended_by": ended_by if ended_by in ENDED_BY else "pause"},
                cost_center=run["center"], actor="dev-console")
    C.set_running(None)
    return ev


def _settle():
    """Close a stretch whose page went quiet (ended_by close, ended at the last ping)."""
    run = C.running() if C else None
    if run and run.get("driver") != "tmux" and (_now() - datetime.fromisoformat(run["last_seen"])).total_seconds() > STALE_SECONDS:
        _close_run("close", now=datetime.fromisoformat(run["last_seen"]))


def _leave(slug: str):
    """A page of another domain opened: a stretch running elsewhere ends (domain_change)."""
    _settle()
    run = C.running() if C else None
    if run and run["domain"] != slug and CLOCK_DRIVER:
        _close_run("domain_change")


def _money_state(slug: str):
    """What the domain's bar draws, or None when the domain has no cost center."""
    center = _center_of(slug)
    if not center:
        return None
    cs, w, now = C.centers(), C.worth(), _now()
    c, rate = cs[center], C.rate_hour(center)
    if not rate:
        return None
    per_day = w.get("paid_hours_day", 5)
    seconds, cost = C.today(center)
    run = C.running()
    live = run if run and run["center"] == center else None
    days = [{"id": cid, "name": cs.get(cid, {}).get("name", cid), "seconds": sec, "cost": cst, "budget_day": C.budget_day(cid)}
            for cid, (sec, cst) in C.today_by_center().items()]
    if center not in {d["id"] for d in days}:
        days.append({"id": center, "name": c.get("name", center), "seconds": 0, "cost": 0.0, "budget_day": C.budget_day(center)})
    investment = c.get("kind") == "investment" or C.budget_day(center) is None  # a client with no day budget has no cap to show
    return {"center": center, "name": c.get("name", center), "investment": investment, "budget": C.budget_day(center),
            "rate": {"minute": rate / 60, "hour": rate, "day": rate * per_day}, "running": bool(live),
            "elapsed": (now - datetime.fromisoformat(live["started_at"])).total_seconds() if live else 0.0,
            "rate_hour_running": live["rate_hour"] if live else rate, "closed_seconds": seconds, "closed_money": cost,
            "idle_minutes": 5, "days": days}




# --- what the pages are drawn from ------------------------------------------------------------------------------
def _default_entity() -> str | None:
    """The entity the domain's own page opens: the newest open one, else the last."""
    entities = journal.read()
    return next((t["id"] for t in reversed(entities) if t.get("status") == "open"), entities[-1]["id"]) if entities else None


def _tabs() -> list[str]:
    """The current domain's modules shown in place: Domain and Task Results are fixed (Task Results when the tasks domain
    is in the console), then the context's TABS. The current domain must already be set (use(slug))."""
    fixed = ["Domain", *(["Task Results"] if "tasks" in DOMAINS else [])]
    return [*fixed, *[t for t in getattr(PROJECT, "TABS", []) if t not in fixed]]


def _page_data(tid: str) -> dict | None:
    """What a domain page embeds as <script id="data"> (minus `money`, `modules` and `domains`, which the server adds).
    None when the entity is unknown. The current domain must already be set (use(slug))."""
    state = journal.read({"id": tid})
    if not state:
        return None
    history = journal.read({"id": tid, "history": True})
    journal_types: dict[str, int] = {}
    for e in journal.read({"history": True}):
        journal_types[e["event"]] = journal_types.get(e["event"], 0) + 1
    tabs = _tabs()
    module_widgets = {n: list(v) for n, v in dict(getattr(PROJECT, "MODULE_WIDGETS", None) or {}).items() if n in tabs}
    return {"base": PROJECT.BASE, "name": PROJECT.NAME, "tabs": tabs, "journal_types": journal_types, "events": history,
            "state": state, "model": real_model(), "entities": PROJECT.ENTITIES, "home": list(getattr(PROJECT, "HOME", ())),
            "module_aliases": dict(getattr(PROJECT, "MODULE_ALIASES", None) or {}), "module_widgets": module_widgets,
            "entity_parts": dict(getattr(PROJECT, "ENTITY_PARTS", None) or {})}


def _rail() -> list[dict]:
    """The entity rail of a domain page, in order: open first, then by update time."""
    out = []
    for t in sorted(journal.read(), key=lambda s: (s.get("status") != "open", s.get("updated_at", ""))):
        out.append({"id": t["id"], "title": PROJECT.title_of(journal.read({"id": t["id"], "history": True}), t),
                    "status": str(t.get("status", "")), "event_count": t.get("event_count")})
    return out


def _info(slug: str, mod) -> dict:
    """What the server needs to know about a domain without asking again."""
    src = Path(mod.SOURCE)
    live_dirs = []
    try:
        live_dirs = [str(Path(d).expanduser()) for d in getattr(mod, "LIVE_DIRS", lambda: [])()]
    except Exception:  # noqa: BLE001
        pass
    return {"slug": slug, "name": mod.NAME, "path": str(Path(mod.__file__).resolve()), "origin": ORIGIN[slug],
            "entity": getattr(mod, "ENTITY", ""), "entity_plural": getattr(mod, "ENTITY_PLURAL", ""),
            "source": str(src), "draft": str(draft_path(mod)), "cost_center": getattr(mod, "COST_CENTER", None),
            "console_home": getattr(mod, "CONSOLE_HOME", None), "media": getattr(mod, "MEDIA", None),
            "actions": sorted(getattr(mod, "ACTIONS", {})), "live_dirs": live_dirs}


def _known(slug: str) -> bool:
    """A domain, or the Playground (the money routes answer for both)."""
    return bool(use(slug)) or (slug == PLAYGROUND_SLUG and slug not in DOMAINS)


def _html(x) -> str:
    return x if isinstance(x, str) else to_xml(x)


# --- the ops ----------------------------------------------------------------------------------------------------
def op_page(a):
    use(a["slug"])
    data = _page_data(a["tid"])
    if not data:
        return None
    t = journal.read({"id": a["tid"]})
    ctx = t.get("context") or {}
    return {**data, "title": PROJECT.title_of(data["events"], t), "entity": PROJECT.ENTITY, "entity_plural": PROJECT.ENTITY_PLURAL,
            "sub": " · ".join(str(ctx[k]) for k in ("project", "version") if k in ctx), "rail": _rail()}


def op_state(a):
    use(a["slug"])
    return _page_data(a.get("task") or _default_entity() or "")


def op_default_entity(a):
    use(a["slug"])
    return {"id": _default_entity(), "empty": not journal.read()}


def op_has_entity(a):
    use(a["slug"])
    try:
        return bool(journal.read())
    except Exception:  # a broken journal must not take the home down
        return False


def op_model(a):
    use(a["slug"])
    return real_model()


def op_widget_list(a):
    use(a["slug"])
    return _html(W.render_list(_ctx(a["tid"], a["event"], a.get("e") or None)))


def op_widget(a):
    slug, tid, event, name = a["slug"], a["tid"], a["event"], a["name"]
    e, mode, domain, task = a.get("e", ""), a.get("mode", "real"), a.get("domain", ""), a.get("task", "")
    use(slug)
    if domain and not task and not e:  # no pick yet: the newest entity of that domain that has this event
        mine = {t["id"] for t in journal.read() if t.get("domain") == domain}
        own = [x for x in journal.read({"event": event}) if x[entity_key()] in mine]
        e = own[-1]["id"] if own else ""
    if task and not e:
        own = [x for x in journal.read({"id": task, "history": True}) if x["event"] == event]
        e = own[-1]["id"] if own else ""
    return _html(W.render_one(_ctx(tid, event, e or None, "sim" if mode == "sim" else "real", domain), name))


def op_action(a):
    use(a["slug"])
    fn = getattr(PROJECT, "ACTIONS", {}).get(a["name"])
    ev = next((e for e in journal.read({"history": True}) if e["id"] == a["eid"]), None)
    if not fn or not ev:
        return _html(P(f"ação {a['name']} ou evento {a['eid'][:8]} não existe", cls="text-neutral-500"))
    return _html(fn(ev, mode="sim" if a.get("mode") == "sim" else "real", step=int(a.get("step") or 0)))


def op_money(a):
    """action: state | enter | start | beat | stop (the same five answers the /time routes gave)."""
    slug, action = a["slug"], a.get("action", "state")
    if not _known(slug):
        return {"status": 404, "body": {"error": "no such domain"}}
    none = {"error": "no cost center"}
    if action == "state":
        _settle() if C else None
        st = _money_state(slug)
        return {"status": 200 if st else 404, "body": st or none}
    if action == "enter":
        if C and CLOCK_DRIVER:
            _leave(slug)
        return {"status": 200, "body": _money_state(slug) or none}
    if action == "start":
        if not CLOCK_DRIVER:  # the window does not drive the clock (tmux-focus does): the bar only shows it
            return {"status": 200, "body": _money_state(slug) or none}
        center = _center_of(slug)
        rate = C.rate_hour(center) if center else None
        if not rate:
            return {"status": 404, "body": none}
        _settle()
        run = C.running()
        if not (run and run["domain"] == slug and run["center"] == center):
            if run:
                _close_run("domain_change")
            now = _now().isoformat(timespec="seconds")
            C.emit("time_entry.started", {"text": C.started_text(center, slug), "domain": slug}, cost_center=center, actor="dev-console")
            C.set_running({"center": center, "domain": slug, "started_at": now, "last_seen": now, "rate_hour": rate})
        return {"status": 200, "body": _money_state(slug)}
    if action == "beat":
        if C and CLOCK_DRIVER:
            _settle()
            run = C.running()
            if run:
                C.set_running({**run, "last_seen": _now().isoformat(timespec="seconds")})
        return {"status": 200, "body": _money_state(slug) or none}
    if action == "stop":
        if C and CLOCK_DRIVER:
            _close_run(a.get("ended_by", "pause"), trim=min(max(float(a.get("trim_seconds") or 0), 0), 86400))
        return {"status": 200, "body": _money_state(slug) or none}
    return {"status": 400, "body": {"error": f"unknown action {action}"}}


def op_money_bar(a):
    """The bar's numbers for a page load (never ends a stretch, never raises): None when the domain has no center."""
    if not C:
        return None
    try:
        return _money_state(a["slug"])
    except Exception:  # noqa: BLE001
        return None


OPS = {"page": op_page, "state": op_state, "default_entity": op_default_entity, "has_entity": op_has_entity,
       "model": op_model, "widget_list": op_widget_list, "widget": op_widget, "action": op_action, "money": op_money,
       "money_bar": op_money_bar}


def main(argv: list[str]) -> None:
    flags = [str(Path(argv[i + 1]).expanduser().resolve()) for i, a in enumerate(argv) if a == "--project"]
    extra = [p for p in os.environ.get("DEV_CONSOLE_REGISTERED", "").split(os.pathsep) if p]
    paths = list(dict.fromkeys(flags + extra))
    out = sys.stdout
    try:
        load_domains(paths, set(flags))
    except Exception:  # noqa: BLE001
        out.write(json.dumps({"op": "ready", "ok": False, "error": traceback.format_exc()}) + "\n")
        out.flush()
        sys.exit(1)
    if not DOMAINS:
        out.write(json.dumps({"op": "ready", "ok": False, "error": "no project loaded"}) + "\n")
        out.flush()
        sys.exit(1)
    CURRENT.set(next(iter(DOMAINS.values())))
    for mod in DOMAINS.values():
        mod.render_screens = render_screens  # the product's real screens, composed (an iframe of its own URL)
        mod.render_expected = render_expected  # actions may render an expected spec too
        mod.render_widget_list = render_widget_list  # WidgetList, composable: the right menu's own list
    for mod in DOMAINS.values():
        write_draft(mod)  # once: the dummy domain draft, if the domain has none yet
    ready = {"op": "ready", "ok": True, "domains": [_info(s, m) for s, m in DOMAINS.items()], "watch": watch_dirs(),
             "catalog": collect(), "costs": bool(C), "clock_driver": CLOCK_DRIVER}
    out.write(json.dumps(ready, ensure_ascii=False, default=str) + "\n")
    out.flush()
    for line in sys.stdin:
        if not line.strip():
            continue
        req = None
        try:
            req = json.loads(line)
            fn = OPS[req["op"]]
            res = {"id": req["id"], "ok": True, "data": fn(req)}
        except Exception:  # noqa: BLE001
            res = {"id": req.get("id") if isinstance(req, dict) else None, "ok": False, "error": traceback.format_exc(limit=6)}
        out.write(json.dumps(res, ensure_ascii=False, default=str) + "\n")
        out.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
