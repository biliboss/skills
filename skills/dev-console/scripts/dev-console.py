# /// script
# requires-python = ">=3.10"
# dependencies = ["python-fasthtml>=0.14", "monsterui>=1.0.48", "watchfiles>=0.21"]
# ///
"""dev-console: a read-only, full-screen console for an event-sourced project in development (FastHTML + MonsterUI).

Run:  uv run --script dev-console.py --project <a/dev_console_project.py> [--project <b/...>] [--port 5057]
Each project file is one domain, served in its own context at /domain/<slug> (SLUG, else the skill folder name).
A project file says what to show (see the skill's references/project-contract.md):
  NAME, SOURCE (file with the EVENTS registry {category: {command: event}}), ENTITY, ENTITY_PLURAL,
  ENTITIES ({category: entity name}), PROJECTOR (the fold function), journal (.read(query)), title_of(), WIDGETS.
Layout: the work area (entity rail on the left, the selected record on the right) and one status line at the bottom
(domain · module · money); ⌘K switches the domain, ⌘P the module (no tab bar). Domain (first tab) = the
domain model (DDD: aggregate root, entities, commands, events); Model = the state machine.
Keys (vim-style goto): g d Domain, g m Model, g v Visão, g p Proposed Actions, g o Observations, g r Relationships,
g t Management, g e Eventos, g y Tipos; Esc closes the popup, then the sidebar. All UI state lives in the query.
A module may be a project widget (MODULE_WIDGETS), and / opens the module a domain names with CONSOLE_HOME (the
Kanban's Quadro), else the first domain.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import importlib.util  # noqa: E402
import os  # noqa: E402
from urllib.parse import quote  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from typing import Any  # noqa: E402


def load_project(path: str):
    """Import the project file (it may import its own code from its folder)."""
    spec = importlib.util.spec_from_file_location("dev_console_project", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec.loader.exec_module(mod)
    return mod


def _sibling(name: str):
    """This script's own module, loaded by its path before any project: load_project puts each project's folder first on
    sys.path, and a project from another checkout of this skill would otherwise hand us that checkout's copy."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # a later `import <name>` gets this one
    spec.loader.exec_module(mod)
    return mod


for _name in ("console_agents", "console_playground", "console_recorder"):
    _sibling(_name)


if "--project" in sys.argv:  # the module body needs the projects, so read the flags before argparse runs
    os.environ["DEV_CONSOLE_PROJECT"] = os.pathsep.join(
        str(Path(sys.argv[i + 1]).expanduser().resolve()) for i, a in enumerate(sys.argv) if a == "--project")
# The domain registry: one dev_console_project.py path per line. Adding a line adds a domain with no restart by hand:
# the watcher sees the file, re-reads it and watches the new project folder too.
REGISTRY = Path(os.environ.get("DEV_CONSOLE_REGISTRY", "~/.local/state/dev-console/domains.txt")).expanduser()


def registered() -> list[str]:
    return [str(Path(l.strip()).expanduser().resolve()) for l in (REGISTRY.read_text().splitlines() if REGISTRY.exists() else [])
            if l.strip() and not l.startswith("#") and Path(l.strip()).expanduser().exists()]


_all = [p for p in os.environ.get("DEV_CONSOLE_PROJECT", "").split(os.pathsep) if p]
os.environ["DEV_CONSOLE_PROJECT"] = os.pathsep.join(dict.fromkeys(_all + registered()))
if not os.environ.get("DEV_CONSOLE_PROJECT"):
    sys.exit("dev-console: pass --project <path/to/dev_console_project.py> (or set DEV_CONSOLE_PROJECT)")

# One domain per project file, each in its own context: /domain/<slug>. A request sets the current domain
# (use(slug)); PROJECT, journal and SOURCE below always read the current one.
from contextvars import ContextVar  # noqa: E402

DOMAINS: dict = {}
ORIGIN: dict = {}  # slug -> "--project" (a flag of this instance) or "registry" (domains.txt); GET /api/domains says it
for _path in os.environ["DEV_CONSOLE_PROJECT"].split(os.pathsep):
    _mod = load_project(_path)
    _slug = getattr(_mod, "SLUG", None) or Path(_path).resolve().parent.parent.name
    _mod.SLUG, _mod.BASE = _slug, f"/domain/{_slug}"  # BASE: the domain's URL prefix (actions build links with it)
    DOMAINS[_slug] = _mod
    ORIGIN[_slug] = "--project" if _path in _all else "registry"
CURRENT: ContextVar = ContextVar("domain", default=next(iter(DOMAINS.values())))


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
from fasthtml.common import H2, A, Button, Div, Iframe, Li, Link, NotStr, P, Script, Span, Style, Title, Ul, fast_app  # noqa: E402
from monsterui.all import Theme  # noqa: E402
from starlette.responses import RedirectResponse  # noqa: E402

# live: every open page reloads on save. `--no-live` (or DEV_CONSOLE_LIVE=0) turns it off, for a second instance
# that one agent drives while another agent saves files: its window never reloads because of someone else's save.
LIVE = "--no-live" not in sys.argv and os.environ.get("DEV_CONSOLE_LIVE", "1") != "0"
app, rt = fast_app(hdrs=Theme.neutral.headers(mode="auto"), live=LIVE)
# DNS rebinding: a page on another domain pointed at 127.0.0.1 would otherwise read /agents/api/prompts. Any other Host
# gets a 400. No CORS is configured anywhere, on purpose: the console is read by its own pages only.
from starlette.middleware.trustedhost import TrustedHostMiddleware  # noqa: E402

import console_agents as _AGH  # noqa: E402  (the allowed host names live with the module that needs them)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=_AGH.allowed_hosts())
journal = _Live(lambda: CURRENT.get().journal)

# The real code, read from disk on every request and pushed again when the file changes.
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
                      + "".join("<tr class='border-t border-neutral-200 dark:border-neutral-800'>"
                                + "".join(f"<td class='py-1 pr-3 font-sans'>{v}</td>" for v in r) + "</tr>" for r in rows)
                      + "</tbody></table>")
    elif kind == "widget":
        fn = getattr(PROJECT, "EXPECTED_WIDGETS", {}).get(spec.get("name", ""))
        body = fn(data or {}) if fn else _empty(f"widget {spec.get('name')} ainda não existe no projeto")
    else:
        body = _empty(f"tipo de saída {kind!r} desconhecido")
    label = spec.get("title") or {"report": "relatório", "list": "lista", "table": "tabela"}.get(kind, spec.get("name", ""))
    return Div(
        Div(Span(spec.get("heading", "Esperado no final"), cls="font-semibold text-neutral-600 dark:text-neutral-300"),
            Span(label if spec.get("heading") else f"{label} · exemplo", cls="text-neutral-400"), cls="flex justify-between gap-3"),
        Div(body, cls="mt-2 text-neutral-700 dark:text-neutral-300"),
        cls="mt-3 rounded border border-dashed border-neutral-300 dark:border-neutral-700 px-3 py-2.5",
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
    btn = "px-2 h-7 rounded border border-neutral-300 dark:border-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900"
    first = steps[0]
    return Div(
        H2(title, cls="mb-3 font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100") if title else "",
        Div(Button("←", type="button", cls=btn, onclick=f"{go}(this,-1)"),
            Span(f"1/{len(steps)} · {first.get('name', '')}", data_n="1", cls="flex-1 min-w-0 truncate text-neutral-700 dark:text-neutral-300"),
            Span(first.get("event") or "", data_e="1", cls="shrink-0 font-mono text-xs text-amber-600 dark:text-amber-400"),
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
        NotStr(f'<svg viewBox="0 0 300 20" class="mt-3 w-full h-5 text-neutral-700 dark:text-neutral-300">'
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
        here = Li(Div(Div(*[Span(cls="w-4 shrink-0 self-stretch border-l border-neutral-300 dark:border-neutral-700 ml-1")
                              for _ in range(depth)],
                          Div(P(name, cls="font-semibold text-neutral-800 dark:text-neutral-200"),
                              P(docs.get(name) or "todo evento", cls="text-neutral-400"), cls="min-w-0"),
                          cls="flex min-w-0 gap-2"),
                      cls="min-w-0"),
           NotStr(f'<button class="w-open shrink-0 px-2 h-7 rounded border border-neutral-300 dark:border-neutral-700 '
                  f'text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900" data-w="{name}" tabindex="-1">abrir</button>'),
           # the whole row opens the widget (click, Enter or Space): a bigger target, and a keyboard stop (WCAG 2.1.1, 2.5.5)
           # no role="button": Pico/MonsterUI paints [role=button] as a blue centred button; the row keeps the list look
           tabindex="0", data_w=name, data_ev=ctx.event, data_base=PROJECT.BASE, aria_haspopup="dialog", aria_label=f"abrir {name}",
           aria_level=str(depth + 1),
           cls="w-row flex items-center justify-between gap-3 px-4 py-3 cursor-pointer border-b border-neutral-200 "
               "dark:border-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:outline-none "
               "focus-visible:bg-neutral-100 dark:focus-visible:bg-neutral-900")
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
for _mod in DOMAINS.values():
    write_draft(_mod)  # once: the dummy domain draft, if the domain has none yet
def entity_key() -> str:
    """The journal field that names the entity, in the current domain."""
    return getattr(PROJECT, "ENTITY_KEY", "tension_id")


CSS = """
#pop-body.sim { background-image: repeating-linear-gradient(135deg, transparent 0 14px, rgba(127,127,127,.06) 14px 15px); }
#pop-body.sim::before { content: "SIMULADO · os botões funcionam, nada é gravado nem enviado"; display: block; margin-bottom: 14px; font-size: 11px; letter-spacing: .12em; color: #8a8a8a; }

html,body{height:100%;overflow:hidden}
/* Nerd Font symbols (Font Awesome range): one small icon before each tab label */
@font-face { font-family: "Symbols Nerd Font Mono"; font-display: swap;
  src: url("https://cdn.jsdelivr.net/gh/ryanoasis/nerd-fonts@v3.2.1/patched-fonts/NerdFontsSymbolsOnly/SymbolsNerdFontMono-Regular.ttf") format("truetype"); }
.nf { font-family: "Symbols Nerd Font Mono"; font-style: normal; display: inline-block; width: 1.25em; margin-right: .3em; text-align: center; opacity: .75; }
/* ?embed=side: the right menu alone, full width (RightMenu widget) */
html[data-embed=side] #graph-col, html[data-embed=side] #ev-close,
html[data-embed=code] #graph-col, html[data-embed=code] #ev-side > div:not(#ev-body) { display: none !important; }
html[data-embed=side] #ev-side { width: 100% !important; border-left: 0; }
/* ?embed=code: the right menu's Code tab alone (Code widget) */
html[data-embed=code] #ev-side { width: 100% !important; border-left: 0; }
html[data-embed=code] #ev-body > details:not([data-part=Code]), html[data-embed=code] #ev-body > details > summary { display: none !important; }
/* ?embed=switcher: the Domain Switcher alone, open (DomainSwitcher widget) */
html[data-embed=switcher] #bar, html[data-embed=switcher] #work { visibility: hidden; }
html[data-embed=switcher] #dom { padding-top: 24px; }
/* ?embed=toolbar: the real status line alone (Toolbar widget) */
html[data-embed=toolbar] #work, html[data-embed=money] #work { display: none !important; }
html[data-embed=toolbar] #bar, html[data-embed=money] #bar { border-top: 0; }
/* the status line: one thin row at the bottom (VS Code, vim); the hint on the right is faint */
#bar [data-ov]{cursor:pointer} #bar [data-ov]:hover{color:rgb(23 23 23)} .dark #bar [data-ov]:hover{color:rgb(245 245 245)}
.rec.sel{background:rgb(229 229 229)} .dark .rec.sel{background:rgb(38 38 38)}
.mermaid svg{max-width:100%}
/* the money bar: one number ticks, the rest is still; an embed never shows it */
#money [data-act]{cursor:pointer} #money [data-act]:focus-visible{outline:1px solid currentColor;outline-offset:2px}
#money .over{color:rgb(220 38 38)} html[data-embed]:not([data-embed=money]) #money{display:none !important}
/* ?embed=money: the money bar alone (CostToolbar widget) */
html[data-embed=money] #bar > :not(#money) { display: none !important; }
html[data-embed=money] #money { border-left: 0; }
/* the right menu's expandable parts: no Pico margins, the chevron right after the title */
#ev-body details { margin: 0; padding: 0; } #ev-body details summary { margin: 0; list-style: none; }
#ev-body details summary::after { float: none; margin-left: .25rem; }
/* a project widget hosted by the console (a module, a sidebar part): the status line or the part already names it,
   so the widget's own leading title hides (it shows in the popup) */
[data-w-host] > div > h2:first-child { display: none; }
"""

JS = r"""
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const D = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
mermaid.initialize({startOnLoad:false, theme:'base', fontFamily:'inherit', themeVariables:{
  primaryColor: dark?'#262626':'#fafafa', primaryBorderColor: dark?'#525252':'#a3a3a3',
  primaryTextColor: dark?'#e5e5e5':'#262626', lineColor: dark?'#737373':'#a3a3a3'}});
window.mermaid = mermaid;  // widgets render their own diagrams (a fenced mermaid block in a report)

const M = () => D.model;  // derived from the project's EVENTS, refreshed live
const E = D.events, byId = Object.fromEntries(E.map(e => [e.id, e]));
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const when = iso => new Date(iso).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const brief = v => v.value ?? v.proposal ?? v.outcome ?? v.conclusion ?? v.statement ?? v.reason ?? v.title ?? v.target ?? JSON.stringify(v);
const of = cat => E.filter(e => e.event.startsWith(cat + '.'));
const label = t => `<p class="text-[11px] uppercase tracking-widest text-neutral-500">${t}</p>`;
const row = (e, cells) => `<div class="rec flex gap-4 px-4 py-2 cursor-pointer border-b border-neutral-100 dark:border-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-900" data-id="${e.id}">${cells}</div>`;
const meta = (e, extra='') => `<span class="w-24 shrink-0 tabular-nums text-neutral-400">${when(e.value.observed_at || e.at)}</span>${extra}`;
const empty = t => `<p class="px-4 py-6 text-neutral-400">${t}</p>`;
const list = (es, cells) => es.length ? es.map((e, i) => row(e, cells(e, i))).join('') : empty('Nada aqui.');
const jsonPre = x => `<pre class="m-0 p-4 !bg-transparent whitespace-pre-wrap text-neutral-600 dark:text-neutral-400">${esc(JSON.stringify(x, null, 2))}</pre>`;

function items() {  // linked things and their last observed state
  const it = {};
  for (const e of E) {
    const v = e.value;
    if (e.event === 'relationship.linked') it[v.target] = {id: v.target, title: v.title || '', state: null, ev: e};
    if (e.event === 'relationship.unlinked') delete it[v.target];
    if (e.event.startsWith('observation.') && v.target in it && v.state) it[v.target].state = v.state;
  }
  return Object.values(it);
}
const isDone = s => ['done','merged','completed','closed'].includes(String(s).toLowerCase());

function proposals() {
  const acts = of('action');
  return acts.filter(e => e.event === 'action.proposed').map(p => {
    const steps = acts.filter(e => e.value.proposal_id === p.id);
    const last = steps.at(-1);
    return {p, steps, status: last ? last.event.split('.')[1] : 'proposed', last};
  });
}
const PT = {proposed:'proposta', started:'em andamento', completed:'concluída', failed:'falhou'};

function renderModel(m) {
  const box = $('model'); if (!box) return;
  $('model-file').textContent = `${m.file} · salvo ${new Date(m.mtime * 1000).toLocaleTimeString('pt-BR')}`;
  box.innerHTML = '<div class="px-2 pb-4 pt-2 leading-6 text-neutral-700 dark:text-neutral-300">' + m.lines.map(l => {
    const pad = (l.code.match(/^ */) || [''])[0].length;
    return `<div class="flex"><span class="w-10 shrink-0 pr-3 text-right select-none text-neutral-300 dark:text-neutral-700">${l.line ?? ''}</span>`
      + `<span class="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]" style="padding-left:${pad + 4}ch;text-indent:-4ch">${codeBlock(l.code.trimStart()) || '&nbsp;'}</span></div>`;
  }).join('') + '</div>';
}
new EventSource(D.base + '/source/stream').onmessage = ev => {
  D.model = JSON.parse(ev.data);
  if (GRAPH(tab) && $('cy')) { drawGraph(); if (side.id) openSide(side.id); }
};

function codeBlock(src) {  // grayscale highlight: weight, not colour
  return src.split('\n').map(l => {
    const i = l.indexOf('#');
    const code = i < 0 ? l : l.slice(0, i), note = i < 0 ? '' : l.slice(i);
    const h = esc(code)
      .replace(/\b(class|def)(\s+)(\w+)/g, '<span class="text-neutral-500">$1</span>$2<span class="font-semibold text-neutral-900 dark:text-neutral-100">$3</span>')
      .replace(/\b(self|cls)\b/g, '<span class="text-neutral-500">$1</span>');
    return h + (note ? `<span class="text-neutral-400">${esc(note)}</span>` : '');
  }).join('\n');
}

let graphRO = null;  // the resize observer of the drawing on screen (a redraw disconnects it)
const layoutKey = () => `dev-console:layout:${D.base}`;
function toggleLayout() {  // `L` only (no button): branch <-> metro (rays), remembered per domain; the name shows as a brief toast
  const m = localStorage.getItem(layoutKey()) || M().layout, next = m === 'branch' ? 'metro' : 'branch';
  localStorage.setItem(layoutKey(), next);
  drawGraph();
  let t = $('layout-toast');
  if (!t) { t = document.createElement('div'); t.id = 'layout-toast';
    t.className = 'fixed right-4 top-4 z-50 px-2 py-1 rounded text-xs bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 pointer-events-none'; document.body.appendChild(t); }
  t.textContent = ({branch: 'ramos', metro: 'raios'})[next]; t.style.display = '';
  clearTimeout(t._h); t._h = setTimeout(() => { t.style.display = 'none'; }, 1200);
}

function drawGraph() {
  if (graphRO) graphRO.disconnect();
  if (window.__cy) { try { window.__cy.destroy(); } catch (e) {} window.__cy = null; }
  const used = {}; E.forEach(e => used[e.event] = (used[e.event] || 0) + 1);
  const ink = dark ? '#f5f5f5' : '#171717', mute = dark ? '#525252' : '#d4d4d4', soft = dark ? '#737373' : '#a3a3a3',
        bg = dark ? '#0a0a0a' : '#ffffff';
  const nodes = [], edges = [];
  const PATH = dark
    ? {management:'#818cf8', observation:'#2dd4bf', reasoning:'#facc15', relationship:'#38bdf8', action:'#fb7185'}
    : {management:'#4338ca', observation:'#0f766e', reasoning:'#a16207', relationship:'#0369a1', action:'#be123c'};
  const PAL = dark ? ['#818cf8', '#2dd4bf', '#facc15', '#38bdf8', '#fb7185', '#a3e635']
                   : ['#4338ca', '#0f766e', '#a16207', '#0369a1', '#be123c', '#4d7c0f'];
  Object.keys(M().lifecycle).forEach((c, i) => { PATH[c] ??= PAL[i % PAL.length]; });
  // the drawing: the person's choice (L toggles branch / metro, kept per domain), else the project's LAYOUT, else metro
  const stored = localStorage.getItem(layoutKey());
  const MODE = stored === 'branch' || stored === 'metro' ? stored : M().layout;
  const BR = MODE === 'branch', METRO = MODE === 'metro' || BR;  // see the METRO and BRANCH blocks below
  let BRINFO = null;  // branch: the lanes' y bands and the stages' x bands, for the headless checks (cy.scratch('branch'))
  if (METRO) Object.keys(M().lifecycle).forEach((c, i) => { PATH[c] = `hsl(${Math.round(i * 137.5) % 360}, ${dark ? 70 : 65}%, ${dark ? 62 : 38}%)`; });
  const colorOf = id => PATH[id.split('.')[0]];
  // Entity.Event: management happens to the Tension itself; the others to the Value Object of their category.
  const ENT = D.entities || {};
  const pascal = w => w.split('_').map(x => x[0].toUpperCase() + x.slice(1)).join('');
  const name = id => { const [c, v] = id.split('.'); return `${ENT[c] || pascal(c)}.${pascal(v)}`; };
  const CENTER = M().hub || M().root;
  const depth = {[CENTER]: 0}, queue = [CENTER];  // rings: steps from the centre (the hub, else created)
  while (queue.length) { const a = queue.shift(); (M().next[a] || []).forEach(b => { if (!(b in depth)) { depth[b] = depth[a] + 1; queue.push(b); } }); }
  Object.entries(M().lifecycle).forEach(([cat, verbs]) => verbs.forEach(v => {
    const id = `${cat}.${v}`;
    nodes.push({data: {id, color: PATH[cat], label: name(id).replace('.', '\n')}, classes: [D.journal_types[id] ? 'used' : '', id === M().root ? 'root' : ''].join(' ')});
  }));
  // ISO 9241-210 (human-centred design): a generic Human is who acts; the first command creates the Tension.
  nodes.push({data: {id: 'human', label: 'Human', color: ink}, classes: 'human'});
  {  // seed: ring = steps from the Human, angle = order; fCoSE refines from here (randomize: false)
    const hd = {human: 0}, q = ['human'], start = M().initial || [M().root];
    start.forEach(s => { hd[s] = 1; q.push(s); }); q.shift();
    while (q.length) { const a = q.shift(); (M().next[a] || []).forEach(b => { if (!(b in hd)) { hd[b] = hd[a] + 1; q.push(b); } }); }
    nodes.forEach((n, i) => { const d = hd[n.data.id] ?? 3, t = 2 * Math.PI * i / nodes.length;
      n.position = d ? {x: Math.cos(t) * d * 160, y: Math.sin(t) * d * 160} : {x: 0, y: 0}; });
  }
  (M().initial || [M().root]).forEach(s => edges.push({data: {id: `human>${s}`, source: 'human', target: s, color: colorOf(s),
    label: M().commands[s]}, classes: D.journal_types[s] ? 'walked' : ''}));
  Object.entries(M().next).forEach(([a, bs]) => bs.forEach(b =>
    edges.push({data: {id: `${a}>${b}`, source: a, target: b, color: colorOf(b), label: (M().edge_cmd || {})[`${a}>${b}`] || M().commands[b]}, classes: [D.journal_types[a] && D.journal_types[b] ? 'walked' : '', (M().next[b] || []).includes(a) ? 'loop' : ''].join(' ')})));
  const STARTS = M().initial || [M().root];
  // each start keeps its own side: what only the left start reaches stays left of the Human, what only the right one
  // reaches stays right, so no edge has to cross the Human (shared nodes, like a hub, go where the forces put them)
  const reach = s => { const seen = new Set([s]), q = [s];
    while (q.length) (M().next[q.shift()] || []).forEach(b => { if (!seen.has(b)) { seen.add(b); q.push(b); } }); return seen; };
  const SIDES = STARTS.length > 1 ? (() => { const L = reach(STARTS[0]), R = reach(STARTS[1]);
    return [...[...L].filter(n => !R.has(n) && n !== STARTS[0]).map(n => ({left: n, right: 'human', gap: 200})),
            ...[...R].filter(n => !L.has(n) && n !== STARTS[1]).map(n => ({left: 'human', right: n, gap: 200}))]; })() : [];
  // LAYOUT = "clock" (project file): the code's EVENTS order is the clock. The first category sits at 12 o'clock and
  // the others follow clockwise; inside a category its events run outward from the Human. The order lives in the
  // code, so the drawing never drifts from it.
  const CLOCK = MODE === 'clock';
  if (CLOCK) {
    const cats = Object.keys(M().lifecycle), N = cats.length;
    const pos = {human: {x: 0, y: 0}};
    cats.forEach((c, i) => { const t = -Math.PI / 2 + 2 * Math.PI * i / N;
      M().lifecycle[c].forEach((v, k) => { const r = 230 + k * 140; pos[`${c}.${v}`] = {x: Math.cos(t) * r, y: Math.sin(t) * r}; }); });
    nodes.forEach(n => { n.position = pos[n.data.id] || {x: 0, y: 0}; });
  }

  // LAYOUT = "metro" (project file): a Tokyo Metro map read from the clock, deterministic (preset positions, no force
  // layout). Octilinear layout, after the metro-map literature (Nöllenburg & Wolff 2011, "Drawing and Labeling
  // High-Quality Metro Maps by Mixed-Integer Programming"): every segment lies on one of 8 directions (multiples of 45°).
  // Each category of EVENTS is a line in its own colour; its clock hour (the first category at 12 o'clock, the others
  // clockwise) snapped to the nearest of the 8 directions says where it leaves the Human. Categories that snap to the
  // same direction are fanned: each next one runs parallel, one TRACK further to the counter-clockwise side. Stations
  // are one constant STEP apart, in EVENTS order, the first one RING from the Human. The label sits on the side of its
  // line that faces away from the Human's middle (right on the right half, left on the left half; below an eastbound
  // line, above a westbound one), always the same side per direction, horizontal text, never rotated; a fanned line
  // runs on the opposite side, so the labels fall in the gap between tracks. A colliding label is pushed outward.
  const STEP = 170, TRACK = 180, HUMAN_R = 56, LABEL_CHARS = 14, LABEL_PUSH = 14;
  const LINE_POINTS = [], DASH_POINTS = [];   // thick line and dashed edge polylines (model coordinates), for the label collision test
  const SHIFT = [0, 1, 0, -1, 0, -1, 0, 1];   // diagonals (NE SE SW NW): the label leaves its own line, down (+1) or up (-1)
  const metroLabelOf = id => { const [c, v] = id.split('.'), ent = ENT[c] || pascal(c);
    const parts = pascal(v).match(/[A-Z][a-z0-9]*|[a-z0-9]+/g) || [pascal(v)], lines = [];
    parts.forEach(p => { const last = lines.length - 1; if (last >= 0 && lines[last].length + p.length <= LABEL_CHARS) lines[last] += p; else lines.push(p); });
    return [ent, ...lines].join('\n'); };
  if (METRO) {
    const DIRS = [[0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1]].map(([x, y]) => { const l = Math.hypot(x, y); return [x / l, y / l]; });
    const SIDE = ['r', 'r', 'b', 'r', 'l', 'l', 't', 'l'];   // N NE E SE S SW W NW: the label's side, fixed per direction
    const FAN = [1, 1, 1, -1, 1, 1, 1, -1];                    // which way a fanned track goes: +1 counter-clockwise, -1 clockwise (never the label's side)
    const cats = Object.keys(M().lifecycle), N = cats.length, dirOf = {}, group = {}, count = {};
    // the clock as the sun's rays: the categories share the whole turn evenly from 12h, in EVENTS order
    cats.forEach((c, i) => { const d = Math.round(8 * i / N) % 8; dirOf[c] = d; group[c] = count[d] || 0; count[d] = group[c] + 1; });
    const BRANCH = HUMAN_R + 4, RING = BRANCH + (Math.max(...Object.values(count)) - 1) * TRACK + 110;   // the fan leaves the Human's rim, then runs straight
    const at = (c, k) => { const [dx, dy] = DIRS[dirOf[c]], o = FAN[dirOf[c]] * group[c] * TRACK, r = RING + k * STEP;   // ccw side = (dy, -dx)
      return {x: dy * o + dx * r, y: -dx * o + dy * r}; };
    const pos = {human: {x: 0, y: 0}}, st = {}, where = {}, parent = {};
    // a line follows TRANSITIONS: a station's parent is its earliest in-line predecessor by a forward edge (EVENTS order;
    // a backward edge, like a reactivation, is a loop and stays a dashed cross edge). Where a station forks, the child
    // with the longest path below it continues the trunk; the others are branches (Tokyo's Marunouchi branch) leaving
    // at 45°, alternating sides, each a STEP further out
    const rot = ([x, y], q) => { const a = q * Math.PI / 4, c = Math.cos(a), sn = Math.sin(a); return [x * c - y * sn, x * sn + y * c]; };
    (BR ? [] : cats).forEach(c => { const vs = M().lifecycle[c], ids = vs.map(v => `${c}.${v}`), k = Object.fromEntries(ids.map((id, i) => [id, i]));
      const kids = Object.fromEntries(ids.map(id => [id, []]));
      ids.forEach(b => { const a = ids.find(a => k[a] < k[b] && edges.some(e => e.data.source === a && e.data.target === b));
        if (a) { parent[b] = a; kids[a].push(b); } });
      const depth = id => 1 + Math.max(0, ...kids[id].map(depth));
      const place = (id, P, dir, n) => { pos[id] = P; where[id] = {c, k: n}; st[id] = {side: SIDE[dirOf[c]], dir: dirOf[c]};
        const ks = [...kids[id]].sort((x, y) => depth(y) - depth(x) || k[x] - k[y]);
        ks.forEach((ch, j) => { const d = j === 0 ? dir : rot(dir, (j % 2 ? 1 : -1)), r = j === 0 ? STEP : STEP * Math.ceil(j / 2) * Math.SQRT2;
          place(ch, {x: P.x + d[0] * r, y: P.y + d[1] * r}, d, n + 1); }); };
      let n = 0; ids.filter(id => !parent[id]).forEach(root => { const P = at(c, n); place(root, P, DIRS[dirOf[c]], n);
        n += 1 + (function trunk(id) { const ks = [...kids[id]].sort((x, y) => depth(y) - depth(x) || k[x] - k[y]); return ks.length ? 1 + trunk(ks[0]) : 0; })(root); }); });
    nodes.forEach(n => { const id = n.data.id; n.position = pos[id] || {x: 0, y: 0};
      if (id !== 'human' && st[id]) { n.classes = (n.classes || '') + ' station'; n.data.mlabel = metroLabelOf(id); n.data.side = st[id].side; n.data.dir = st[id].dir; } });
    // a segment route: from S through the bends Bs to T; cytoscape wants each bend as a weight and a distance:
    // point = S + w (T - S) + d (-dy, dx) / |T - S|
    const route = (S, T, Bs) => { const dx = T.x - S.x, dy = T.y - S.y, L2 = dx * dx + dy * dy;
      return {w: Bs.map(B => ((B.x - S.x) * dx + (B.y - S.y) * dy) / L2), d: Bs.map(B => ((B.y - S.y) * dx - (B.x - S.x) * dy) / Math.sqrt(L2))}; };
    const octi = (S, T, skip) => { const dx = T.x - S.x, dy = T.y - S.y, m = Math.min(Math.abs(dx), Math.abs(dy));
      if (m < 1 || Math.abs(Math.abs(dx) - Math.abs(dy)) < 1) return null;   // already 0 / 45 / 90: straight
      // one bend, two ways: the diagonal first or the straight run first; keep the one that stays clear of the Human
      // and of the other stations (a route through them reads as a line through them)
      const diag = {x: S.x + Math.sign(dx) * m, y: S.y + Math.sign(dy) * m};
      const run = {x: S.x + (Math.abs(dx) > Math.abs(dy) ? Math.sign(dx) * (Math.abs(dx) - m) : 0),
                   y: S.y + (Math.abs(dy) > Math.abs(dx) ? Math.sign(dy) * (Math.abs(dy) - m) : 0)};
      const cost = B => { let c = 0; [[S, B], [B, T]].forEach(([p, q]) => { const len = Math.hypot(q.x - p.x, q.y - p.y);
        for (let t = 0; t <= len; t += 8) { const x = p.x + (q.x - p.x) * t / len, y = p.y + (q.y - p.y) * t / len;
          if (Math.hypot(x, y) < HUMAN_R + 16) c += 3;
          Object.entries(pos).forEach(([id, o]) => { if (id !== 'human' && id !== skip[0] && id !== skip[1] && Math.hypot(x - o.x, y - o.y) < 18) c += 1; }); } }); return c; };
      return cost(run) < cost(diag) ? run : diag; };
    const stub = c => { const [dx, dy] = DIRS[dirOf[c]], o = group[c] * TRACK;   // leaves the trunk at the Human's rim, a 45° leg into its track
      const track = at(c, 0), run = {x: track.x - dx * (RING - BRANCH - o), y: track.y - dy * (RING - BRANCH - o)};   // where the leg meets the track
      return o ? [{x: dx * BRANCH, y: dy * BRANCH}, run] : null; };
    const adjacent = (a, b) => parent[b] === a;
    const made = new Set();
    // LAYOUT = "branch" (project file, or `L` on any domain): a git graph read left to right (`git log --graph`, the most
    // familiar flow drawing). The Human is the root, at the top left. Each category of EVENTS is a horizontal lane (a
    // branch), top to bottom in EVENTS order; inside a lane a line follows TRANSITIONS as the metro does (the longest path
    // is the trunk, a fork drops into a short 45° spur inside the lane, a back edge is a dashed arrow). A lane is born
    // where its transition comes from: its first station sits one column right of the station that leads into it, joined
    // by a 45° connector (a vertical gutter between two 45° legs when the lane is far below); a lane nothing leads into
    // starts from the Human along a grey spine. Any other edge into another lane is a merge: thin, grey, dashed, one bend,
    // with its command label. Columns are the funnel stages when the project declares STAGES and STAGE_ORDER (a band of
    // columns per stage, a faint header at the top, a station inside its stage's band, ordered by the path); without
    // them a column is the longest step count from the Human. Labels are horizontal, below the station (above on a
    // spur that rises), pushed apart by the same collision pass as the metro.
    const COL = 170, SPURY = 72, GAP = 40, LANE_ABOVE = 80, LANE_BELOW = 88, LANE_PAD = 34, LANE_SKIP = 12, HEADER = 84;
    const branchLayout = () => {
      const lanes = cats.map(c => ({c, ids: M().lifecycle[c].map(v => `${c}.${v}`)})), laneOf = {};
      lanes.forEach((l, i) => l.ids.forEach(id => { laneOf[id] = i; }));
      const adj = {}; edges.forEach(e => { (adj[e.data.source] ??= []).push(e.data.target); });
      // reverse post-order of a depth-first walk from the Human (then from what it does not reach, in lane order): every
      // edge but the back edges (loops) points forward, so a longest path gives the columns
      // the walk also follows the order of each lane (a station before the next one), so a station that nothing leads
      // to is placed after the one before it
      const walkAdj = Object.fromEntries(Object.entries(adj).map(([a, bs]) => [a, [...bs]]));
      lanes.forEach(l => l.ids.slice(1).forEach((id, i) => { (walkAdj[l.ids[i]] ??= []).push(id); }));
      const seen = new Set(), onStack = new Set(), back = new Set();
      const dfs = (a, out) => { seen.add(a); onStack.add(a);
        (walkAdj[a] || []).forEach(b => { if (onStack.has(b)) back.add(`${a}>${b}`); else if (!seen.has(b)) dfs(b, out); });
        onStack.delete(a); out.push(a); };
      const order = ['human', ...lanes.flatMap(l => l.ids)].flatMap(r => { if (seen.has(r)) return []; const out = []; dfs(r, out); return out.reverse(); });
      // the funnel stages (STAGES, STAGE_ORDER): columns are bands, one per stage. An edge that goes back to an earlier
      // stage would run leftwards: it is a loop, a dashed arrow, like any back edge
      const ST = M().stages || {}, SO = [...(M().stage_order || [])];
      Object.values(ST).forEach(s => { if (!SO.includes(s)) SO.push(s); });
      const staged = SO.length > 0; if (!staged) SO.push('');
      if (staged) edges.forEach(e => { const a = e.data.source, b = e.data.target;
        if (ST[a] != null && ST[b] != null && SO.indexOf(ST[b]) < SO.indexOf(ST[a])) back.add(`${a}>${b}`); });
      // the stage of a station is STAGES[id]; one that is not named takes its parent's or its predecessors' latest,
      // else the previous station of its lane
      const preds = {}; edges.forEach(e => { const a = e.data.source, b = e.data.target;
        if (a !== b && !back.has(`${a}>${b}`)) (preds[b] ??= []).push(a); });
      // inside a lane: a station's parent is its earliest in-lane predecessor by a forward edge; the longest path below a
      // fork stays on the lane's row, the other children drop (below first, then above, then further) into a 45° spur
      const parentOf = {}, kidsOf = {}, slot = {};
      lanes.forEach(l => { const k = Object.fromEntries(l.ids.map((id, i) => [id, i]));
        l.ids.forEach(id => { kidsOf[id] = []; });
        l.ids.forEach(b => { const a = l.ids.find(a => k[a] < k[b] && (preds[b] || []).includes(a)); if (a) { parentOf[b] = a; kidsOf[a].push(b); } });
        const dep = id => 1 + Math.max(0, ...kidsOf[id].map(dep));
        const walk = (id, s) => { slot[id] = s; [...kidsOf[id]].sort((x, y) => dep(y) - dep(x) || k[x] - k[y])
          .forEach((ch, j) => walk(ch, j === 0 ? s : s + (j % 2 ? 1 : -1) * Math.ceil(j / 2))); };
        l.ids.filter(id => !parentOf[id]).forEach(r => walk(r, 0)); });
      const stage = {}, local = {}, occ = new Set();
      const prevOf = id => { const l = lanes[laneOf[id]], i = l.ids.indexOf(id); return i > 0 ? l.ids[i - 1] : null; };
      order.forEach(id => { if (id === 'human') return;
        let s = staged && ST[id] != null ? SO.indexOf(ST[id]) : -1;
        if (s < 0) { const ps = (preds[id] || []).filter(a => stage[a] != null).map(a => stage[a]), pv = prevOf(id);
          s = stage[parentOf[id]] ?? (ps.length ? Math.max(...ps) : (pv && stage[pv] != null ? stage[pv] : 0)); }
        stage[id] = s; });
      // a column inside the stage's band: one right of its latest predecessor in the same stage; a later root of a lane
      // continues from the station before it; two stations never share a lane row and a column
      order.forEach(id => { if (id === 'human') return;
        let base = Math.max(0, ...(preds[id] || []).filter(a => a !== 'human' && local[a] != null && stage[a] === stage[id]).map(a => local[a] + 1));
        const pv = prevOf(id); if (!parentOf[id] && pv && local[pv] != null && stage[pv] === stage[id]) base = Math.max(base, local[pv] + 1);
        const key = c => `${laneOf[id]}|${slot[id]}|${stage[id]}|${c}`; while (occ.has(key(base))) base++;
        occ.add(key(base)); local[id] = base; });
      const width = SO.map(() => 0); Object.keys(local).forEach(id => { width[stage[id]] = Math.max(width[stage[id]], local[id] + 1); });
      const bandStart = []; let cc = 1; SO.forEach((s, i) => { bandStart[i] = cc; cc += width[i]; });
      const xOf = id => (bandStart[stage[id]] + local[id]) * COL + stage[id] * GAP;
      // the lanes, top to bottom in EVENTS order; the Human sits on the first lane's row
      let y = 0; lanes.forEach(l => { const ss = l.ids.map(id => slot[id]), lo = Math.min(...ss), hi = Math.max(...ss);
        l.top = y; l.row = y + (lo < 0 ? -lo * SPURY + LANE_ABOVE : LANE_PAD); l.bottom = l.row + hi * SPURY + LANE_BELOW; y = l.bottom + LANE_SKIP; });
      const y0 = lanes[0].row;
      lanes.forEach(l => { l.top -= y0; l.row -= y0; l.bottom -= y0; l.ids.forEach(id => { pos[id] = {x: xOf(id), y: l.row + slot[id] * SPURY}; }); });
      nodes.forEach(n => { const id = n.data.id; if (id === 'human') return;
        n.position = pos[id]; n.classes = (n.classes || '') + ' station'; n.data.mlabel = metroLabelOf(id);
        n.data.side = slot[id] < 0 ? 't' : 'b'; n.data.dir = 2; n.data.lane = laneOf[id]; n.data.stage = SO[stage[id]]; });
      const top = lanes[0].top - (staged ? HEADER : 0), bottom = lanes[lanes.length - 1].bottom;
      const bands = SO.map((s, i) => ({stage: s, x1: bandStart[i] * COL + i * GAP - COL / 2, x2: (bandStart[i] + width[i]) * COL + i * GAP - COL / 2}));
      if (staged) bands.forEach((b, i) => { if (!width[i]) return;
        nodes.unshift({data: {id: `stage:${i}`, label: (M().stage_labels || {})[b.stage] ?? b.stage, w: b.x2 - b.x1, h: bottom - top, tone: i % 2 ? 0.05 : 0.025},
          position: {x: (b.x1 + b.x2) / 2, y: (top + bottom) / 2}, classes: 'stagehdr', selectable: false, grabbable: false}); });
      BRINFO = {lanes: lanes.map(l => ({cat: l.c, y1: l.top, y2: l.bottom, row: l.row, ids: l.ids})), bands: staged ? bands.filter((b, i) => width[i]) : [],
        stage: Object.fromEntries(Object.entries(stage).map(([id, i]) => [id, SO[i]]))};
      // the edges. A lane's birth: the transition into its first station from the leftmost source outside the lane
      lanes.forEach(l => { l.first = l.ids.find(id => !parentOf[id]); });
      const birth = {};
      lanes.forEach((l, i) => { const ps = (preds[l.first] || []).filter(a => laneOf[a] !== i).sort((a, b) => pos[a].x - pos[b].x); if (ps.length) birth[l.first] = ps[0]; });
      const kindOf = (a, b) => parentOf[b] === a ? 'inlane'
        : (laneOf[b] != null && lanes[laneOf[b]].first === b && birth[b] === a && !back.has(`${a}>${b}`)) ? 'branch' : 'merge';
      // a spur leaves its parent at 45° and then runs along its own row; the others bend once
      const spurRoute = (a, b) => { const S = pos[a], T = pos[b], dy = T.y - S.y, dx = T.x - S.x;
        if (Math.abs(dy) < 1) return [];
        if (Math.abs(dy) < dx - 1) return [{x: S.x + Math.abs(dy), y: T.y}];
        const B = octi(S, T, [a, b]); return B ? [B] : []; };
      // a branch from a station far below (or above) leaves at 45°, drops along its own gutter, and enters its lane at 45°;
      // each branch leaving the same station takes its own gutter, the farthest lane the innermost, so they never cross
      const groups = {};
      edges.forEach(e => { const a = e.data.source, b = e.data.target;
        if (a !== 'human' && a !== b && kindOf(a, b) === 'branch') (groups[`${a}|${Math.sign(pos[b].y - pos[a].y)}`] ??= {a, bs: []}).bs.push(b); });
      const gutter = {};
      Object.values(groups).forEach(({a, bs}) => bs.sort((p, q) => Math.abs(pos[q].y - pos[a].y) - Math.abs(pos[p].y - pos[a].y))
        .forEach((b, i) => { gutter[`${a}>${b}`] = Math.min(46 + i * 26, COL - 40); }));  // a full track apart: 10 px read as one line
      const branchRoute = (a, b) => { const S = pos[a], T = pos[b], dy = T.y - S.y, dx = T.x - S.x, s = Math.sign(dy);
        if (a === 'human') return Math.abs(dy) >= dx ? [{x: 0, y: T.y - s * dx}] : spurRoute(a, b);
        const h = gutter[`${a}>${b}`];
        if (Math.abs(dy) < COL || dx < COL - 1 || h == null) return spurRoute(a, b);
        const Bs = [{x: S.x + h, y: S.y + s * h}, {x: S.x + h, y: T.y - s * (COL - h)}, {x: S.x + COL, y: T.y}];
        if (dx - COL < 1) Bs.pop(); return Bs; };
      // the interchange: lines leaving one station down (or up) a 45° leg are ranked by the leg's length; rank k leaves
      // k·PAR lower-left of the centre (source-endpoint) and turns 2·k·PAR earlier, so the legs are parallel tracks
      const PAR = 9, legs = {}, rank = {};
      const rawBs = (a, b) => { const k = kindOf(a, b); return k === 'merge' || a === 'human' || a === b ? [] : k === 'inlane' ? spurRoute(a, b) : branchRoute(a, b); };
      edges.forEach(e => { const a = e.data.source, b = e.data.target, B = rawBs(a, b)[0]; if (!B) return;
        const lx = B.x - pos[a].x, ly = B.y - pos[a].y; if (lx < 1 || Math.abs(Math.abs(ly) - lx) > 1) return;
        (legs[`${a}|${Math.sign(ly)}`] ??= []).push({b, lx}); });
      Object.entries(legs).forEach(([key, ls]) => { const a = key.split('|')[0];
        ls.sort((p, q) => q.lx - p.lx).forEach((l, k) => { rank[`${a}>${l.b}`] = k; }); });
      const shifted = (a, b, Bs) => { const k = rank[`${a}>${b}`] || 0; if (!k || !Bs.length) return Bs;
        const sg = Math.sign(Bs[0].y - pos[a].y) || 1, d = 2 * k * PAR, nx = Bs[1] || pos[b];
        const horiz = Math.abs(nx.y - Bs[0].y) < 1;  // a leg that then runs along a row turns earlier; one that drops, lower
        return [horiz ? {x: Bs[0].x - d, y: Bs[0].y} : {x: Bs[0].x, y: Bs[0].y + sg * d}, ...Bs.slice(1)]; };
      const done = new Set(), born = new Set();
      edges.forEach(e => { const a = e.data.source, b = e.data.target, cl = (e.classes || '').replace(/\bloop\b/, '').trim();
        if (a === b) return;
        const kind = kindOf(a, b); done.add(`${a}>${b}`); let Bs = [];
        if (kind === 'merge' && back.has(`${a}>${b}`)) {  // a loop runs leftwards: an arc above the rows, never along a line
          const dx = Math.abs(pos[b].x - pos[a].x), dy = pos[b].y - pos[a].y;
          e.classes = `${cl} cross backloop`; e.data.cpd = (pos[b].x <= pos[a].x ? 1 : -1) * (SPURY * 0.9 + Math.min(dx, 4 * COL) * 0.12 + Math.abs(dy) * 0.1); }
        else if (kind === 'merge') { e.classes = `${cl} cross`; const B = octi(pos[a], pos[b], [a, b]); Bs = B ? [B] : []; DASH_POINTS.push([pos[a], ...Bs, pos[b]]); }
        else { Bs = shifted(a, b, kind === 'inlane' ? spurRoute(a, b) : branchRoute(a, b)); e.data.label = '';
          const k = rank[`${a}>${b}`] || 0, sg = Math.sign(pos[b].y - pos[a].y) || 1;
          if (k) e.data.sep = `${-k * PAR}px ${sg * k * PAR}px`;
          const spine = a === 'human' && Math.abs(pos[b].y - pos[a].y) >= 1;
          e.classes = `${cl} ${spine ? 'spine' : 'line'}${e.data.sep ? ' parallel' : ''}`; if (spine) e.data.color = soft; if (kind === 'branch') born.add(b);
          LINE_POINTS.push([k ? {x: pos[a].x - k * PAR, y: pos[a].y + sg * k * PAR} : pos[a], ...Bs, pos[b]]); }  // the shifted start, for the label test
        if (Bs.length) e.data.route = route(pos[a], pos[b], Bs); });
      // a lane is continuous: where the model has no edge between a station and the one before it, a faint rail carries the
      // line on; a lane nothing leads into hangs from the Human on the grey spine
      const rail = (a, b, color, cls, Bs) => { edges.push({data: {id: `rail:${a}>${b}`, source: a, target: b, color, label: '', ...(Bs.length ? {route: route(pos[a], pos[b], Bs)} : {})}, classes: cls});
        LINE_POINTS.push([pos[a], ...Bs, pos[b]]); };
      lanes.forEach(l => { const pairs = l.ids.slice(1).map(id => [parentOf[id] || prevOf(id), id]).filter(([a, b]) => a !== b && !done.has(`${a}>${b}`));
        if (!born.has(l.first)) pairs.unshift(['human', l.first]);
        pairs.forEach(([a, b]) => { if (a === 'human') { const far = Math.abs(pos[b].y) >= 1; rail(a, b, far ? soft : PATH[l.c], far ? 'spine' : 'rail', far ? branchRoute(a, b) : []); }
          else rail(a, b, PATH[l.c], 'rail', spurRoute(a, b)); }); });
    };
    if (BR) branchLayout();
    (BR ? [] : edges).forEach(e => { const a = e.data.source, b = e.data.target, cl = (e.classes || '').replace(/\bloop\b/, '').trim();
      made.add(`${a}>${b}`);
      const lineEdge = a === 'human' ? where[b] && where[b].k === 0 : adjacent(a, b);
      if (lineEdge) { e.classes = `${cl} line`; e.data.label = ''; const c = where[b].c;
        const Bs = a === 'human' ? stub(c) : null;
        if (Bs) { e.data.route = route(pos[a], pos[b], Bs); LINE_POINTS.push([pos[a], ...Bs, pos[b]]); } else LINE_POINTS.push([pos[a], pos[b]]); }
      else { e.classes = `${cl} cross`; const B = octi(pos[a], pos[b], [a, b]); if (B) e.data.route = route(pos[a], pos[b], [B]); } });
    // a line is continuous: where the model has no edge between two neighbours (or the Human and the first station)
    // a faint rail carries the line on, so the category still reads as one track
    (BR ? [] : cats).forEach(c => { const ids = M().lifecycle[c].map(v => `${c}.${v}`), c0 = ids[0];
      // only roots after the first have no parent: a later root continues the trunk from the station before it
      const pairs = ids.slice(1).map(id => [parent[id] || ids[Math.max(0, ids.indexOf(id) - 1)], id]).filter(([a, b]) => a !== b);
      if (!made.has(`human>${c0}`)) pairs.unshift(['human', c0]);
      pairs.forEach(([a, b]) => { if (made.has(`${a}>${b}`)) return;
        const Bs = a === 'human' ? stub(c) : null;
        edges.push({data: {id: `rail:${a}>${b}`, source: a, target: b, color: PATH[c], label: '', ...(Bs ? {route: route(pos[a], pos[b], Bs)} : {})}, classes: 'rail'});
        LINE_POINTS.push(Bs ? [pos[a], ...Bs, pos[b]] : [pos[a], pos[b]]); }); });
  }
  const cy = cytoscape({
    // the wheel is ours (below the layout): two fingers pan, a pinch or ⌘ + scroll zooms, as in Figma and Maps
    container: $('cy'), elements: {nodes, edges}, userZoomingEnabled: false,
    // fCoSE: force-directed, the Human pinned in the centre; seeded (randomize false + fixed seed positions) so a
    // reload draws the same picture. nodeRepulsion and idealEdgeLength leave room for the edge labels.
    layout: (CLOCK || METRO) ? {name: 'preset', padding: 24} : {name: 'fcose', quality: 'proof', randomize: false, animate: false, padding: 24,
             nodeDimensionsIncludeLabels: true, idealEdgeLength: () => 130, nodeRepulsion: () => 45000,
             edgeElasticity: () => 0.45, gravity: 0.4, gravityRange: 2.5, numIter: 5000, nodeSeparation: 90,
             fixedNodeConstraint: [{nodeId: 'human', position: {x: 0, y: 0}}],
             // the starts sit in line with the Human, one on each side; what follows them hangs below
             ...(STARTS.length > 1 ? {alignmentConstraint: {horizontal: [['human', ...STARTS]]},
               relativePlacementConstraint: [{left: STARTS[0], right: 'human', gap: 160}, {left: 'human', right: STARTS[1], gap: 160}, ...SIDES,
                 ...(M().hub ? [{top: 'human', bottom: M().hub, gap: 140},
                   ...(M().next[M().hub] || []).map(b => ({top: M().hub, bottom: b, gap: 90}))] : [])]} : {})}, maxZoom: 3,
    style: [
      {selector: 'node', style: {shape: 'round-rectangle', width: n => Math.max(...n.data('label').split('\n').map(l => l.length)) * 10 + 28, height: 56,
        'text-wrap': 'wrap', 'line-height': 1.3,
        'background-color': bg, 'border-width': 1.5, 'border-color': 'data(color)', 'border-opacity': 0.7,
        label: 'data(label)', 'text-valign': 'center', 'font-family': 'ui-monospace, monospace',
        'font-size': 16, color: 'data(color)'}},
      {selector: 'node.used', style: {'background-color': 'data(color)', 'border-width': 0, color: bg, 'font-weight': 700}},
      {selector: 'node.root', style: {'font-size': 19, width: n => Math.max(...n.data('label').split('\n').map(l => l.length)) * 12 + 36, height: 66}},
      // UML initial pseudostate: a filled dot, named Human (who triggers the first transition).
      // the Human is the centre of every domain: twice an event node's height (56)
      {selector: 'node.human', style: {shape: 'ellipse', width: 112, height: 112, 'background-color': ink,
        'border-width': 0, color: ink, 'font-size': 22, 'font-weight': 700, 'text-valign': 'bottom', 'text-margin-y': 12,
        'font-family': 'ui-sans-serif, system-ui'}},
      {selector: 'edge', style: {label: 'data(label)', 'font-family': 'ui-monospace, monospace', 'font-size': 15,
        color: 'data(color)', 'text-background-color': bg, 'text-background-opacity': 1, 'text-background-padding': '3px',
        'text-rotation': 'autorotate'}},
      {selector: 'edge', style: {width: 2, 'line-color': 'data(color)', 'target-arrow-color': 'data(color)',
        'target-arrow-shape': 'triangle', 'arrow-scale': 0.8, 'curve-style': 'straight', 'line-opacity': 0.45}},
      {selector: 'edge.walked', style: {width: 3.5, 'line-opacity': 1}},
      // a loop (A -> B and B -> A, from TRANSITIONS): two curved edges, side by side, so neither hides the other
      {selector: 'edge.loop', style: {'curve-style': 'bezier', 'control-point-step-size': 60}},
      ...(METRO ? [
        {selector: 'node.station', style: {shape: 'ellipse', width: 16, height: 16, 'background-color': bg, 'border-width': 3,
          'border-color': 'data(color)', 'border-opacity': 1, label: 'data(mlabel)', 'font-size': 14, 'font-weight': 400,
          color: dark ? '#a3a3a3' : '#525252', 'text-wrap': 'wrap', 'line-height': 1.15, 'text-valign': 'center', 'text-halign': 'center'}},
        {selector: 'node.station.used', style: {'background-color': 'data(color)', 'border-width': 0, width: 18, height: 18, color: ink}},
        {selector: 'node.station[side="r"]', style: {'text-halign': 'right', 'text-valign': 'center', 'text-justification': 'left'}},
        {selector: 'node.station[side="l"]', style: {'text-halign': 'left', 'text-valign': 'center', 'text-justification': 'right'}},
        {selector: 'node.station[side="b"]', style: {'text-halign': 'center', 'text-valign': 'bottom', 'text-justification': 'center'}},
        {selector: 'node.station[side="t"]', style: {'text-halign': 'center', 'text-valign': 'top', 'text-justification': 'center'}},
        {selector: 'node.human', style: {'text-valign': 'center', color: bg, 'text-margin-y': 0, 'font-size': 20}},
        {selector: 'edge.line', style: {width: 6, 'line-color': 'data(color)', 'line-opacity': 1, 'target-arrow-shape': 'none', label: '', 'z-index': 3}},
        {selector: 'node.stagehdr', style: {shape: 'rectangle', width: 'data(w)', height: 'data(h)', 'background-color': ink, 'background-opacity': 'data(tone)',
          'border-width': 0, label: 'data(label)', 'text-valign': 'top', 'text-halign': 'center', 'text-margin-y': 40, 'font-size': 20, 'font-weight': 600,
          'font-family': 'ui-sans-serif, system-ui', color: soft, 'text-opacity': 0.85, events: 'no', 'z-index': 0}},
        {selector: 'edge.spine', style: {width: 4, 'line-color': soft, 'line-opacity': 0.55, 'target-arrow-shape': 'none', label: '', events: 'no', 'z-index': 1}},
        {selector: 'edge.rail', style: {width: 6, 'line-color': 'data(color)', 'line-opacity': 0.5, 'target-arrow-shape': 'none', label: '', events: 'no', 'z-index': 1}},
        {selector: 'edge.parallel', style: {'source-endpoint': 'data(sep)'}},
        {selector: 'edge.backloop', style: {'curve-style': 'unbundled-bezier', 'control-point-distances': 'data(cpd)', 'control-point-weights': 0.5, 'z-index': 1}},
        {selector: 'edge.cross', style: {width: 2, 'line-color': soft, 'line-style': 'dashed', 'line-dash-pattern': [7, 5], 'line-opacity': 0.9,
          'target-arrow-color': soft, 'target-arrow-shape': 'triangle', 'arrow-scale': 1, color: soft, 'font-size': 14, 'text-rotation': 'none', 'z-index': 2}},
      ] : []),
      {selector: ':selected', style: {'border-width': 4, 'border-color': ink, 'border-opacity': 1}},
    ],
  });
  if (METRO) {
    // octilinear routes: a bend point per edge that needs one (computed above as weight and distance)
    cy.edges().forEach(e => { const r = e.data('route'); if (!r) return;
      e.style({'curve-style': 'segments', 'segment-weights': r.w, 'segment-distances': r.d, 'edge-distances': 'node-position'}); });
    // labels: the clockwise side first; a label that touches another label, a station or a line is pushed outward
    const box = (n, labels) => n.boundingBox({includeNodes: !labels, includeEdges: false, includeLabels: !!labels, includeOverlays: false});
    const hit = (a, b, m) => a.x1 - m < b.x2 && b.x1 - m < a.x2 && a.y1 - m < b.y2 && b.y1 - m < a.y2;
    const bodies = cy.nodes().not('.stagehdr').map(n => ({id: n.id(), b: box(n, false)}));
    const onLine = (bx, set = LINE_POINTS) => set.some(pts => pts.slice(1).some((p, i) => { const q = pts[i], len = Math.hypot(p.x - q.x, p.y - q.y);
      for (let t = 0; t <= len; t += 4) { const x = q.x + (p.x - q.x) * t / len, y = q.y + (p.y - q.y) * t / len;
        if (x > bx.x1 - 4 && x < bx.x2 + 4 && y > bx.y1 - 4 && y < bx.y2 + 4) return true; } return false; }));
    const uni = (a, b) => ({x1: Math.min(a.x1, b.x1), y1: Math.min(a.y1, b.y1), x2: Math.max(a.x2, b.x2), y2: Math.max(a.y2, b.y2)});
    const placed = [], unions = [], PUSH = {r: [1, 0], l: [-1, 0], b: [0, 1], t: [0, -1]};
    cy.nodes('.station').forEach(n => {
      const pref = n.data('side'), dir = n.data('dir'), cands = BR ? [pref, pref === 'b' ? 't' : 'b'] : [pref];   // branch: a station that branches downwards may carry its label above
      let best = null;
      for (const side of cands) {
        n.data('side', side);
        const [px, py] = PUSH[side], h = box(n, true), lh = h.y2 - h.y1;
        let mx = px * 9, my = py * 9;
        // on a diagonal the label centred on the station would sit on its own line: shift it off, to the clockwise side
        if (SHIFT[dir]) my += SHIFT[dir] * (lh / 2 + 3);
        for (let i = 0; i < 10; i++) {
          n.style({'text-margin-x': mx, 'text-margin-y': my});
          const lb = box(n, true);   // the label alone (includeNodes false)
          const ub = uni(lb, box(n, false));
          const hits = placed.filter(p => hit(p, lb, 4)).length + unions.filter(p => hit(p, ub, 2)).length
            + bodies.filter(o => o.id !== n.id() && hit(o.b, ub, 3)).length + (onLine(lb) || onLine(lb, DASH_POINTS) ? 1 : 0);
          if (!best || hits < best.hits) best = {hits, side, m: [mx, my]};   // never worse than the least-clashing step
          if (!hits) break;
          mx += px * LABEL_PUSH; my += py * LABEL_PUSH;
        }
        if (best.hits === 0) break;
      }
      n.data('side', best.side); n.style({'text-margin-x': best.m[0], 'text-margin-y': best.m[1]});
      placed.push(box(n, true)); unions.push(uni(box(n, true), box(n, false)));
    });
    // a dashed edge's label (the command): the midpoint first, then nudged around it until it clears everything
    const eplaced = [], NUDGE = [];
    for (let dy = -224; dy <= 224; dy += 16) for (let dx = -224; dx <= 224; dx += 28) NUDGE.push([dx, dy]);   // a grid around the midpoint, nearest first
    NUDGE.sort((a, b) => Math.hypot(...a) - Math.hypot(...b));
    cy.edges('.cross').forEach(e => { if (!e.data('label')) return;
      let best = null, bestHits = 1e9;
      for (const [nx, ny] of NUDGE) { e.style({'text-margin-x': nx, 'text-margin-y': ny});
        const lb = e.boundingBox({includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false});
        const hits = placed.filter(p => hit(p, lb, 3)).length + eplaced.filter(p => hit(p, lb, 3)).length
          + unions.filter(p => hit(p, lb, 3)).length + bodies.filter(o => hit(o.b, lb, 3)).length + (onLine(lb) ? 1 : 0);
        if (hits < bestHits) { bestHits = hits; best = [nx, ny]; } if (!hits) break; }
      e.style({'text-margin-x': best[0], 'text-margin-y': best[1]});
      eplaced.push(e.boundingBox({includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false})); });
  }
  // Legible at his window: no label renders below 14 px on screen. Font sizes are in model units, so the zoom has a
  // floor (14 / the smallest label's font); fit, the home view and a pinch stop there, and a big domain opens larger
  // than the window, read by panning. Nothing is hidden or resized: every label keeps the room the layout gave it.
  const LEGIBLE = 14, fonts = cy.elements().filter(e => e.style('label')).map(e => parseFloat(e.style('font-size')));
  if (fonts.length) cy.minZoom(Math.min(cy.maxZoom(), LEGIBLE / Math.min(...fonts)));
  // The wheel, as in Figma and Maps: two fingers (or a mouse wheel) pan; a pinch zooms around the pointer (Chrome and
  // Firefox send it as wheel + ctrlKey; WebKit, the native window, as gesture events), and so does ⌘ + scroll.
  const pane = $('cy'), at = e => { const r = pane.getBoundingClientRect();
    return Number.isFinite(e.clientX) ? {x: e.clientX - r.left, y: e.clientY - r.top} : {x: r.width / 2, y: r.height / 2}; };
  const zoomTo = (z, e) => cy.zoom({level: Math.min(cy.maxZoom(), Math.max(cy.minZoom(), z)), renderedPosition: at(e)});
  let pinch = 0;   // the zoom when a WebKit pinch began; 0 = none
  pane.addEventListener('wheel', e => {
    e.preventDefault();   // the page never scrolls under the graph
    const k = e.deltaMode === 1 ? 40 : e.deltaMode === 2 ? cy.height() : 1;   // lines, pages or pixels
    let dx = e.deltaX * k, dy = e.deltaY * k;
    if (e.ctrlKey || e.metaKey) {   // a pinch is small steps; a ctrl or ⌘ mouse notch is capped at about a quarter
      if (!pinch) zoomTo(cy.zoom() * Math.exp(-Math.max(-0.3, Math.min(0.3, dy * (e.ctrlKey ? 0.01 : 0.002)))), e);
      return; }
    if (e.shiftKey && !dx) [dx, dy] = [dy, 0];   // shift + mouse wheel goes sideways
    cy.panBy({x: -dx, y: -dy});
  }, {passive: false});
  pane.addEventListener('gesturestart', e => { e.preventDefault(); pinch = cy.zoom(); });
  pane.addEventListener('gesturechange', e => { e.preventDefault(); if (pinch && e.scale) zoomTo(pinch * e.scale, e); });
  pane.addEventListener('gestureend', e => { e.preventDefault(); pinch = 0; });
  let box = '';
  graphRO = new ResizeObserver(([e]) => {
    const k = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;
    if (k === box || !e.contentRect.width) return;  // same size: do nothing (this guard stops the flicker loop)
    box = k; cy.resize(); cy.fit(undefined, 20); centreHuman();
  });
  graphRO.observe($('cy'));
  // open centred on the Human (fit keeps the zoom, then the Human goes to the middle); off centre, a button brings it back
  // branch: the Human at the top left with a margin, the zoom fitting the height down to the legible floor (pan to read on)
  function homeView() {
    const bb = cy.elements().boundingBox({includeLabels: true, includeOverlays: false}), m = 40;
    const zoom = Math.max(cy.minZoom(), Math.min(1, (cy.height() - 2 * m) / Math.max(bb.y2 - bb.y1, 1)));   // the legible floor
    return {zoom, pan: {x: m - bb.x1 * zoom, y: m - bb.y1 * zoom}};
  }
  function centreHuman() {
    const h = cy.$('#human'); if (h.empty()) { offCentre(); return; }
    if (BR) { const v = homeView(); cy.zoom(v.zoom); cy.pan(v.pan); offCentre(); return; }
    cy.center(h);
    // centred on the Human, every node must still show: zoom out around the Human until the farthest one fits
    const bb = cy.elements().renderedBoundingBox(), cx = cy.width() / 2, cy0 = cy.height() / 2, pad = 24;
    const k = Math.min(1, (cx - pad) / Math.max(cx - bb.x1, bb.x2 - cx, 1), (cy0 - pad) / Math.max(cy0 - bb.y1, bb.y2 - cy0, 1));
    if (k < 1) cy.zoom({level: cy.zoom() * k, renderedPosition: {x: cx, y: cy0}});
    offCentre();
  }
  function offCentre() {
    const h = cy.$('#human'), b = $('centre-human'); if (!b || h.empty()) return;
    const p = h.renderedPosition(), v = BR ? homeView() : null,
      tx = v ? h.position().x * v.zoom + v.pan.x : cy.width() / 2, ty = v ? h.position().y * v.zoom + v.pan.y : cy.height() / 2,
      far = Math.hypot(p.x - tx, p.y - ty) > 40;
    b.classList.toggle('hidden', !far);
  }
  cy.on('pan zoom', offCentre);
  cy.ready(centreHuman);
  if ($('centre-human')) $('centre-human').onclick = () => cy.animate(BR ? {zoom: homeView().zoom, pan: homeView().pan, duration: 250, complete: offCentre}
    : {center: {eles: cy.$('#human')}, duration: 250, complete: offCentre});
  cy.scratch('branch', BRINFO);
  $('legend').innerHTML = Object.entries(PATH).filter(([c]) => c in M().lifecycle).map(([c, col]) => `<span style="color:${col}">● ${c}</span>`).join('')
    + '';
  cy.on('tap', ev => { if (ev.target === cy) closeSide(); });
  cy.on('tap', 'node', ev => { if (Q.get('embed') !== 'graph') openSide(ev.target.id()); });  // embed=graph: the graph alone
  window.__cy = cy;
}

// --- the event sidebar: contextual, with its own tabs -----------------------------------------------------
// UI state lives in the URL query: tab, ev (event in the sidebar), side (sidebar tab), w (widget popup).
const Q = new URLSearchParams(location.search);
function setQ(k, v) { v ? Q.set(k, v) : Q.delete(k); const q = Q.toString();
  history.replaceState(null, '', location.pathname + (q ? '?' + q : '')); }
let side = {id: null, tab: Q.get('side') || 'Widgets'};
const SIDE_TABS = {
  // Description: what the event means, for a human: the code comment of its command in EVENTS
  'Description': id => Promise.resolve((M().descriptions || {})[id]
    ? `<p class="px-4 py-2 font-sans text-[15px] leading-relaxed text-neutral-800 dark:text-neutral-200">${esc(M().descriptions[id])}</p>`
    : '<p class="px-4 py-2 text-neutral-400">sem descrição: escreva um comentário no comando, em EVENTS</p>'),
  'Widgets': id => frag(`${D.base}/w/${D.state.id}/${id}?e=${Q.get('e') || ''}`),
  // Code: pseudo-code of the clicked event's context, read from the real model (EVENTS, the projector): the command
  // that records it, where it comes from and what it opens, and the entity it changes. Short on purpose.
  'Code': id => {
    const m = M(), ENT = D.entities || {}, [c, v] = id.split('.');
    const P = w => w.split('_').map(x => x[0].toUpperCase() + x.slice(1)).join('');
    const nm = e => { const [k, x] = e.split('.'); return `${ENT[k] || P(k)}.${P(x)}`; };
    const from = Object.entries(m.next).filter(([, bs]) => bs.includes(id)).map(([a]) => nm(a));
    if ((m.initial || [m.root]).includes(id)) from.unshift('Human');
    const to = (m.next[id] || []).map(nm), cmd = m.commands[id];
    const at = (m.lines.find(l => l.code.trim().startsWith(`def ${cmd}(`)) || {}).line;
    const root = m.root.split('.')[0], ent = ENT[c] || P(c);
    // Subsections, in order of relevance: the entity (the command and its class) and the value object this event
    // carries open by default; the other value objects, then the types (enums) last, closed. Each item remembers
    // being opened or closed in localStorage, by name, so it stays that way on every node.
    const line = (n, code) => {
      const hit = code.trim().startsWith(`def ${cmd}(`) || n === at && n != null;
      const pad = (code.match(/^ */) || [''])[0].length;
      return `<div class="flex ${hit ? 'bg-neutral-200 dark:bg-neutral-800' : ''}"><span class="w-10 shrink-0 pr-3 text-right select-none text-neutral-300 dark:text-neutral-700">${n ?? ''}</span>`
        + `<span class="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]" style="padding-left:${pad + 4}ch;text-indent:-4ch">${codeBlock(code.trimStart()) || '&nbsp;'}</span></div>`;
    };
    const key = name => `dev-console:code:${D.base}:${name}`;
    const item = (name, label, rows, open) => {
      const saved = localStorage.getItem(key(name)), isOpen = saved ? saved === 'open' : open;
      return `<details data-code-item="${esc(name)}" ${isOpen ? 'open' : ''} class="mb-1">`
        + `<summary class="flex items-center gap-2 px-2 h-7 cursor-pointer select-none text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100">${label}</summary>`
        + `<div class="pb-2">${rows.map(([n, code]) => line(n, code)).join('')}</div></details>`;
    };
    const group = title => `<div class="px-2 pt-3 pb-1 text-[11px] uppercase tracking-widest text-neutral-400">${title}</div>`;
    const entityRows = [
      [at, `${ent}.${cmd}(value) -> ${nm(id)}`],
      [null, `    from  ${from.join(', ') || '—'}`],
      [null, `    then  ${to.join(', ') || '—'}`],
      [null, ''],
      [null, `class ${ent}:  # ${c === root ? 'the aggregate root, folded by the projector' : 'held by ' + (ENT[root] || P(root))}`],
      ...(c === root ? [[null, `    ${(m.props || []).join(', ')}`]] : []),
      ...Object.entries(m.commands).filter(([e]) => e.startsWith(c + '.')).map(([e, k]) => [null, `    def ${k}(value) -> ${nm(e)}`]),
    ];
    const vos = m.value_objects || [];
    const voRows = vo => [[vo.line, `@value class ${vo.name}:  # ${vo.doc}`], ...vo.fields.map(([f, t, ln]) => [ln, `    ${f}: ${t}`])];
    const mine = vos.filter(vo => !vo.members && vo.event === id);
    const others = vos.filter(vo => !vo.members && vo.event !== id);
    const types = vos.filter(vo => vo.members);
    const html = item(`entity:${ent}`, `${ent} · ${cmd}`, entityRows, true)
      + mine.map(vo => item(`vo:${vo.name}`, `${vo.name} · o valor de ${nm(id)}`, voRows(vo), true)).join('')
      + (others.length ? group('Value objects') + others.map(vo => item(`vo:${vo.name}`, vo.name, voRows(vo), false)).join('') : '')
      + (types.length ? group('Tipos') + types.map(vo => item(`type:${vo.name}`, `${vo.name} <span class="text-neutral-400">· ${esc(vo.members.join(' | '))}</span>`,
          [[vo.line, `@enum ${vo.name}: ${vo.members.join(' | ')}  # ${vo.doc}`]], false)).join('') : '');
    // save only what the person toggles (a click on the summary), never the default state of a first render
    setTimeout(() => document.querySelectorAll('[data-code-item] > summary').forEach(s => s.onclick = () => {
      const d = s.parentElement; setTimeout(() => localStorage.setItem(key(d.dataset.codeItem), d.open ? 'open' : 'closed'), 0); }), 0);
    return Promise.resolve(`<p class="px-4 pt-3 text-neutral-400">pseudo-código · de ${esc(m.file)} · ao vivo</p><div class="px-2 py-2 leading-6 text-neutral-700 dark:text-neutral-300">${html}</div>`);
  },
  'JSON': id => Promise.resolve(jsonPre(E.filter(e => e.event === id))),
  // every event has it, so it is a tab of the right menu (the last), not a widget in the list
  'Observability': id => frag(`${D.base}/w/${D.state.id}/${id}/Observability?e=${Q.get('e') || ''}`).then(h => `<div class="p-4">${h}</div>`),
};
function openSide(id) {
  side.id = id; setQ('ev', id);
  $('ev-side').classList.remove('hidden');
  if (id === 'human') {
    $('ev-name').textContent = 'Human';
    $('ev-sub').textContent = 'estado inicial · ISO 9241-210';
    $('ev-tabs').innerHTML = '';
    $('ev-body').innerHTML = `<p class="p-4 font-sans text-sm text-neutral-700 dark:text-neutral-300">Quem age. Começa por ${(M().initial || [M().root]).map(s => `<b>${M().commands[s]}</b> (grava ${s})`).join(' ou ')}.</p>`;
    return;
  }
  const [c, v] = id.split('.'), n = E.filter(e => e.event === id).length, w = (M().coverage || {})[id] || [];
  $('ev-name').textContent = `${c}.${v}`;
  $('ev-sub').textContent = `comando ${M().commands[id]} · ${n} ${n === 1 ? 'evento' : 'eventos'} · ${w.length ? `${w.length} ${w.length === 1 ? 'widget' : 'widgets'}` : 'sem widgets'}`;
  renderSide();
}
// The right menu is a column of expandable parts (Widgets only when the event has widgets; Code, JSON, and
// Observability last, since every event has it). Every part starts open; each node remembers which parts the user
// closed, in localStorage (key per domain, event and part).
const sideParts = id => Object.keys(SIDE_TABS).filter(t => t !== 'Widgets' || ((M().coverage || {})[id] || []).length);
const partKey = (id, p) => `dev-console:part:${D.base}:${id}:${p}`;
// one expandable part of the sidebar, the same markup for an event's parts and an entity's (a module's card)
const partHtml = (p, open) => `<details data-part="${esc(p)}" ${open ? 'open' : ''}
      class="border-b border-neutral-200 dark:border-neutral-800">
      <summary class="flex items-center gap-2 px-4 h-9 cursor-pointer select-none text-[11px] uppercase tracking-widest text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100">${esc(p)}</summary>
      <div class="part-body pb-2"><p class="px-4 text-neutral-400">carregando…</p></div></details>`;
function renderSide() {
  const want = side.id, parts = sideParts(want);
  $('ev-tabs').innerHTML = '';
  $('ev-body').innerHTML = parts.map(p => partHtml(p, localStorage.getItem(partKey(want, p)) !== 'closed')).join('');
  $('ev-body').querySelectorAll('details').forEach(d => d.ontoggle = () =>
    d.open ? localStorage.removeItem(partKey(want, d.dataset.part)) : localStorage.setItem(partKey(want, d.dataset.part), 'closed'));
  parts.forEach(p => SIDE_TABS[p](want).then(html => {
    if (side.id !== want) return;
    const el = $('ev-body').querySelector(`details[data-part="${p}"] .part-body`);
    inject(el, html);
    if (p === 'Widgets') wireRows(el, want);
    if (p === 'Code') {  // scroll only the sidebar to the event's command (scrollIntoView would also scroll #main)
      const hit = el.querySelector('#hit'), body = $('ev-body');
      if (hit) body.scrollTop = hit.offsetTop - body.clientHeight / 2;
    }
  }));
}

const frag = u => fetch(u, {headers: {'HX-Request': 'true'}}).then(r => r.text());
// --- Switcher overlay: fuzzy subsequence match (fzf-style), matched letters in bold. One finder, two lists:
// ⌘K the domains only (Enter opens /domain/<slug>), ⌘P the modules (D.modules: Domain, TABS, Playground) ---------
// In DevConsole.app the chrome is native: its palette (⌘K / ⌘P through the menu, a click on the status line) replaces
// this overlay, which stays off there. A plain browser (and every headless agent) keeps it.
const IN_APP = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.devconsole);
let domSel = 0, domHits = [], ovMode = 'domain';
function fuzzy(q, s) {  // every letter of q, in order, inside s; a lower score is a tighter match
  q = q.toLowerCase(); const low = s.toLowerCase(); let i = -1, last = -1, gaps = 0; const at = [];
  for (const ch of q) { i = low.indexOf(ch, i + 1); if (i < 0) return null; if (last >= 0) gaps += i - last - 1; at.push(i); last = i; }
  return {score: gaps + (at[0] || 0), at};
}
const ovItems = () => ovMode === 'module'
  ? D.modules.map(m => ({name: m.name, href: m.href, tag: m.href ? '' : [COUNT[m.name] ? COUNT[m.name]() : '', KEYS[m.name] ? 'g ' + KEYS[m.name] : ''].filter(Boolean).join('  '),
      cur: m.href ? m.href === D.module : m.name === tab}))
  : D.domains.map(d => ({name: d.name, href: `/domain/${d.slug}`, tag: d.entity, cur: d.slug === D.base.split('/').pop()}));
function domRender() {
  const q = $('dom-q').value.trim();
  domHits = ovItems().map(d => ({d, m: fuzzy(q, d.name)})).filter(x => x.m).sort((a, b) => a.m.score - b.m.score);
  domSel = Math.min(domSel, Math.max(domHits.length - 1, 0));
  $('dom-list').innerHTML = domHits.length ? domHits.map(({d, m}, i) => {
    const name = [...d.name].map((ch, k) => m.at.includes(k) ? `<b class="text-neutral-900 dark:text-neutral-100">${esc(ch)}</b>` : esc(ch)).join('');
    return `<div class="dom-row flex items-center justify-between gap-4 px-4 h-9 cursor-pointer ${i === domSel ? 'bg-neutral-100 dark:bg-neutral-900' : ''}" data-i="${i}">
      <span class="text-neutral-600 dark:text-neutral-400">${name}${d.cur ? '<span class="ml-2 text-neutral-400">· atual</span>' : ''}</span>
      <span class="text-neutral-400">${esc(d.tag)}</span></div>`;
  }).join('') : `<p class="px-4 h-9 leading-9 text-neutral-400">nenhum ${ovMode === 'module' ? 'módulo' : 'domínio'}</p>`;
  $('dom-list').querySelectorAll('.dom-row').forEach(r => { r.onclick = () => { domSel = +r.dataset.i; domGo(); }; r.onmousemove = () => { if (domSel !== +r.dataset.i) { domSel = +r.dataset.i; domRender(); } }; });
}
const domGo = () => {  // an href navigates; a module with none (a tab of this domain) is shown in place
  const h = domHits[domSel]; if (!h) return;
  if (h.d.href) { location.href = h.d.href; return; }
  domClose(); show(h.d.name);
};
const domIsOpen = () => !$('dom').classList.contains('hidden');
function domOpen(mode = 'domain') {
  if (IN_APP) { window.webkit.messageHandlers.devconsole.postMessage({palette: mode === 'module' ? 'modules' : 'domains'}); return; }  // the native palette
  ovMode = mode; $('dom-q').placeholder = mode === 'module' ? 'módulo…' : 'domínio…';
  $('dom').classList.remove('hidden'); $('dom').classList.add('flex'); $('dom-q').value = ''; domSel = 0; domRender(); $('dom-q').focus();
}
function domClose() { if (Q.get('embed') === 'switcher') return; $('dom').classList.add('hidden'); $('dom').classList.remove('flex'); }
const ovToggle = mode => { if (domIsOpen() && ovMode === mode) domClose(); else domOpen(mode); };
window.devconsoleModules = () => ovToggle('module');  // the native app's ⌘P menu item (⌘P is Print in AppKit) calls these
window.devconsoleDomains = () => ovToggle('domain');
$('dom-open').onclick = () => domOpen('domain');
if ($('mod-open')) $('mod-open').onclick = () => domOpen('module');
$('dom').onclick = e => { if (e.target === $('dom')) domClose(); };
$('dom-q').oninput = () => { domSel = 0; domRender(); };
$('dom-q').onkeydown = e => {
  if (e.key === 'ArrowDown' || (e.ctrlKey && e.key === 'n')) { domSel = Math.min(domSel + 1, domHits.length - 1); domRender(); e.preventDefault(); }
  else if (e.key === 'ArrowUp' || (e.ctrlKey && e.key === 'p')) { domSel = Math.max(domSel - 1, 0); domRender(); e.preventDefault(); }
  else if (e.key === 'Enter') { domGo(); e.preventDefault(); }
  else if (e.key === 'Escape') { domClose(); e.preventDefault(); e.stopPropagation(); }
};
document.addEventListener('keydown', e => {
  if (!(e.metaKey || e.ctrlKey)) return;
  const k = e.key.toLowerCase();
  if (IN_APP) { if (k === 'p' || k === 'k') e.preventDefault(); return; }  // the app's menu owns both keys: nothing on the page
  if (k === 'k') { ovToggle('domain'); e.preventDefault(); }
  else if (k === 'p') {
    e.preventDefault();  // never the browser's print panel
    if (e.ctrlKey && !e.metaKey && e.target === $('dom-q')) return;  // inside the finder Ctrl+P is "up"
    if (!Q.get('embed')) ovToggle('module');
  }
}, true);  // capture: a canvas (tldraw) that stops the key in its own handlers must not eat ⌘K and ⌘P
function wireRows(el, ev) {  // a WidgetList row opens its widget: click anywhere on it, or Enter / Space when focused
  el.querySelectorAll('.w-row').forEach(r => {
    const go = () => openWidget(ev || r.dataset.ev, r.dataset.w, ev ? D.base : r.dataset.base);
    r.onclick = go;
    r.onkeydown = k => { if (k.key === 'Enter' || k.key === ' ') { k.preventDefault(); go(); } };
  });
}
function inject(el, h) {
  el.innerHTML = h;
  el.querySelectorAll('script').forEach(o => { const n = document.createElement('script'); n.textContent = o.textContent; o.replaceWith(n); });
  if (window.htmx) htmx.process(el);
}
const MODE = () => Q.get('mode') === 'sim' ? 'sim' : 'real';
function paintMode() {
  document.querySelectorAll('#pop-mode .mode').forEach(m => {
    const on = m.dataset.mode === MODE();
    m.classList.toggle('font-semibold', on);
    m.classList.toggle('bg-neutral-900', on); m.classList.toggle('text-white', on);
    m.classList.toggle('dark:bg-neutral-100', on); m.classList.toggle('dark:text-neutral-900', on);
    m.classList.toggle('text-neutral-500', !on);
  });
  $('pop-body').classList.toggle('sim', MODE() === 'sim');
}
document.querySelectorAll('#pop-mode .mode').forEach(m => m.onclick = () => {
  setQ('mode', m.dataset.mode === 'sim' ? 'sim' : '');
  const id = Q.get('ev'), name = Q.get('w');
  if (id && name) openWidget(id, name);
});
function openWidget(id, name, base = D.base) {
  setQ('w', name); paintMode();
  $('pop-mode').classList.remove('hidden');
  $('pop-name').textContent = name;
  $('pop-sub').textContent = Q.get('e') ? `${id} · evento ${Q.get('e').slice(0, 8)}` : `${id} · primeiro evento real do diário`;
  $('pop-body').innerHTML = '<p class="text-neutral-400">carregando…</p>';
  $('pop').classList.remove('hidden'); $('pop').classList.add('flex');
  frag(`${base}/w/${D.state.id}/${id}/${encodeURIComponent(name)}?e=${base === D.base ? Q.get('e') || '' : ''}&mode=${MODE()}`).then(h => {
    inject($('pop-body'), h);
    // a widget generated from a real source (data-real-only: a SKILL.md, the code) has nothing to simulate: no REAL | SIMULADO
    if ($('pop-body').querySelector('[data-real-only]')) { setQ('mode', ''); $('pop-mode').classList.add('hidden'); }
    // a composed WidgetList inside the popup: its abrir opens that widget here (in its own domain)
    wireRows($('pop-body'));
  });
}
function closeWidget() { setQ('mode', ''); setQ('w', ''); $('pop').classList.add('hidden'); $('pop').classList.remove('flex'); }
const popOpen = () => !$('pop').classList.contains('hidden');
$('pop-close').onclick = closeWidget;
$('pop').onclick = e => { if (e.target === $('pop')) closeWidget(); };
function closeSide() { side.id = null; setQ('ev', ''); setQ('side', ''); setQ('w', ''); setQ('e', ''); setQ('ent', ''); markEntity(null);
  const el = $('ev-side'); if (el) el.classList.add('hidden'); }

// The contextual sidebar: one markup for every view that opens it (a graph node, a module's entity)
const SIDE_HTML = `<aside id="ev-side" class="hidden w-[min(380px,34vw)] shrink-0 flex flex-col border-l border-neutral-200 dark:border-neutral-800">
        <div class="shrink-0 flex items-start justify-between gap-3 px-4 pt-3 pb-2">
          <div class="min-w-0"><p id="ev-name" class="font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100"></p>
            <p id="ev-sub" class="text-neutral-400"></p></div>
          <button id="ev-close" title="Esc" class="shrink-0 px-1.5 text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100">✕</button></div>
        <div id="ev-tabs" class="shrink-0 flex px-2 border-b border-neutral-200 dark:border-neutral-800"></div>
        <div id="ev-body" class="relative flex-1 min-h-0 overflow-y-auto"></div>
      </aside>`;

const TABS = {
  // Domain (DDD, Evans 2003) is the first tab and reuses the Model graph and sidebar: one graph, one style.
  'Domain': () => TABS['Model'](),
  // Task Results (fixed, second): the tasks executed for this domain, from the tasks domain's own Tasks widget (composed)
  'Task Results': () => '<div id="task-results" class="h-full overflow-auto px-6 py-5"><p class="text-neutral-400">carregando…</p></div>',
  'Model': () => `<div class="h-full flex">
      <div id="graph-col" class="flex-1 min-w-0 flex flex-col">
        <div class="flex items-center gap-4 px-4 pt-3 min-w-0">
          <span id="legend" class="flex flex-wrap gap-x-3 gap-y-1 text-neutral-400 min-w-0"></span>
          <span class="ml-auto shrink-0 cursor-help text-neutral-500" title="Máquina de estados a partir do Human · aresta: comando (transição) · nó: evento (estado alcançado) · cheio: já no diário">?</span></div>
        <div class="relative flex-1 min-h-0"><div id="cy" class="absolute inset-0"></div>
          <button id="centre-human" class="hidden absolute right-3 bottom-3 z-10 px-3 py-1.5 rounded-md text-sm border border-neutral-300 dark:border-neutral-700 bg-white/90 dark:bg-neutral-900/90 text-neutral-700 dark:text-neutral-200 hover:text-neutral-950 dark:hover:text-white">◎ Centralizar Human</button></div>
      </div>
      ${SIDE_HTML}</div>`,
  'Visão': () => {
    if (D.home.length) return `<div id="home" class="max-w-4xl px-8 py-8"><p class="text-neutral-400">carregando…</p></div>`;
    const it = items(), done = it.filter(i => isDone(i.state)).length, ps = proposals();
    let g = 'flowchart LR\n  hoje(["Hoje"])\n  desejado(["Desejado"])\n';
    it.forEach((i, n) => {
      const mark = i.state ? (isDone(i.state) ? '✓ ' : '● ') : '';
      g += `  w${n}["${mark}${i.id}"]\n  hoje --- w${n} --> desejado\n  class w${n} ${i.state ? (isDone(i.state) ? 'done' : 'open') : 'none'}\n`;
    });
    g += '  classDef done stroke-dasharray:3 3,color:#a3a3a3\n  classDef open stroke-width:2px,font-weight:600\n  classDef ends font-weight:600,stroke-width:2px\n  class hoje,desejado ends';
    return `<div class="max-w-3xl px-8 py-8 font-sans">
      ${label('Hoje')}<p class="mt-2 text-lg leading-8 text-neutral-800 dark:text-neutral-200">${esc(D.state.actual)}</p>
      <div class="mt-8">${label('Desejado')}<p class="mt-2 text-lg leading-8 text-neutral-800 dark:text-neutral-200">${esc(D.state.desired)}</p></div>
      <div class="mt-10 grid grid-cols-3 gap-6 border-y border-neutral-200 dark:border-neutral-800 py-5">
        <div>${label('Trabalho ligado')}<p class="mt-1 text-2xl font-semibold tabular-nums">${done} <span class="text-neutral-400 font-normal">de ${it.length}</span></p></div>
        <div>${label('Observações')}<p class="mt-1 text-2xl font-semibold tabular-nums">${of('observation').length}</p></div>
        <div>${label('Propostas')}<p class="mt-1 text-2xl font-semibold tabular-nums">${ps.length} <span class="text-neutral-400 font-normal">· ${ps.filter(x => x.status === 'completed').length} concluída(s)</span></p></div>
      </div>
      <pre class="mermaid mt-8 !bg-transparent">${g}</pre></div>`;
  },
  'Proposed Actions': () => {
    const ps = proposals();
    if (!ps.length) return empty('Nenhuma proposta ainda.');
    return ps.map(({p, steps, last}, n) => row(p,
      `<span class="w-6 shrink-0 text-neutral-400 tabular-nums">${n + 1}</span>
       <div class="min-w-0 flex-1 font-sans">
         <p class="text-sm leading-6 text-neutral-900 dark:text-neutral-100">${esc(p.value.proposal ?? brief(p.value))}</p>
         <p class="mt-1 text-xs text-neutral-400">${['proposed', ...steps.map(s => s.event.split('.')[1])].map((s, i, a) =>
            `<span class="${i === a.length - 1 ? 'font-semibold text-neutral-700 dark:text-neutral-300' : ''}">${PT[s]}</span>`).join(' → ')}
            · ${esc(p.actor)} · ${when(p.at)}</p>
         ${last && last.value.outcome ? `<p class="mt-2 text-sm text-neutral-600 dark:text-neutral-400">${esc(last.value.outcome)}</p>` : ''}
       </div>`)).join('');
  },
  'Observations': () => list(of('observation').slice().reverse(), e =>
    meta(e, `<span class="w-20 shrink-0 text-neutral-500">${esc(e.value.source || e.actor)}</span>
             <span class="flex-1 min-w-0 font-sans text-sm text-neutral-800 dark:text-neutral-200">${esc(brief(e.value))}</span>
             ${e.event !== 'observation.recorded' ? `<span class="text-neutral-500">${e.event.split('.')[1]}</span>` : ''}`)),
  'Relationships': () => {
    const it = items();
    if (!it.length) return empty('Nada ligado.');
    return it.map(i => row(i.ev,
      `<span class="w-5 shrink-0 text-neutral-500">${i.state ? (isDone(i.state) ? '✓' : '●') : '·'}</span>
       <span class="w-20 shrink-0 font-semibold">${esc(i.id)}</span>
       <span class="flex-1 min-w-0 truncate font-sans text-sm ${isDone(i.state) ? 'text-neutral-400' : 'text-neutral-800 dark:text-neutral-200'}">${esc(i.title)}</span>
       <span class="text-neutral-500">${esc(i.state || '')}</span>`)).join('');
  },
  'Management': () => list(of('management'), e =>
    meta(e, `<span class="w-24 shrink-0 text-neutral-500">${e.event.split('.')[1]}</span>
             <span class="flex-1 min-w-0 font-sans text-sm text-neutral-800 dark:text-neutral-200">${esc(e.value.reason || e.value.title || e.value.actual || brief(e.value))}</span>`)),
  'Eventos': () => list(E, (e, i) =>
    `<span class="w-6 shrink-0 text-right text-neutral-400 tabular-nums">${i + 1}</span>${meta(e)}
     <span class="w-56 shrink-0 font-semibold text-neutral-700 dark:text-neutral-300">${e.event}</span>
     <span class="w-10 shrink-0 text-neutral-500">${esc(e.actor)}</span>
     <span class="flex-1 min-w-0 truncate text-neutral-500">${esc(brief(e.value))}</span>`),
  'Tipos': () => {
    const used = {}; E.forEach(e => used[e.event] = (used[e.event] || 0) + 1);
    return `<div class="px-4 py-4 grid grid-cols-5 gap-6">` + Object.entries(M().lifecycle).map(([cat, verbs]) =>
      `<div>${label(cat)}<div class="mt-2 space-y-1">${verbs.map(v => {
        const k = `${cat}.${v}`;
        return `<div class="flex justify-between ${used[k] ? 'font-semibold text-neutral-800 dark:text-neutral-200' : 'text-neutral-400'}"><span>${v}</span><span>${used[k] || ''}</span></div>`;
      }).join('')}</div></div>`).join('') + `</div>`;
  },
};
const COUNT = {'Proposed Actions': () => proposals().length, 'Observations': () => of('observation').length,
  'Relationships': () => items().length,
  'Management': () => of('management').length, 'Eventos': () => E.length};

const GRAPH = t => t === 'Domain' || t === 'Model';  // tabs drawn by drawGraph
const KEYS = {'Domain': 'd', 'Task Results': 'k', 'Model': 'm', 'Visão': 'v', 'Proposed Actions': 'p', 'Observations': 'o', 'Relationships': 'r',
              'Management': 't', 'Eventos': 'e', 'Tipos': 'y'};
// Nerd Font icon per tab (Font Awesome codepoints: sitemap, cubes, eye, lightbulb, search, link, cog, list, tags)
const ICON = {'Domain': '\uf0e8', 'Task Results': '\uf00c', 'Model': '\uf1b3', 'Visão': '\uf06e', 'Proposed Actions': '\uf0eb', 'Observations': '\uf002',
              'Relationships': '\uf0c1', 'Management': '\uf013', 'Eventos': '\uf03a', 'Tipos': '\uf02c'};
const nf = t => ICON[t] ? `<i class="nf">${ICON[t]}</i>` : '';
const keyed = t => { const k = KEYS[t]; if (!k) return t; const i = t.toLowerCase().indexOf(k);
  return i < 0 ? t : `${t.slice(0, i)}<span class="underline underline-offset-4">${t[i]}</span>${t.slice(i + 1)}`; };
// --- a module drawn by one of the project's widgets (MODULE_WIDGETS: the Kanban's Quadro): full width, its leading
// title hidden (the status line names it), beside the same contextual sidebar. An element of it with data-entity opens
// that sidebar for its entity (click, Enter, Space): the project's ENTITY_PARTS widgets rendered for it, then its JSON;
// ?ent= keeps it open across a reload. Its goto key is the first free letter of its name.
const MW = D.module_widgets || {};
const isModule = t => Object.prototype.hasOwnProperty.call(MW, t);
Object.keys(MW).forEach(name => {
  TABS[name] = () => `<div class="h-full flex"><div id="module-view" data-w-host class="flex-1 min-w-0 min-h-0 overflow-auto">
      <p class="px-4 py-3 text-neutral-400">carregando…</p></div>${SIDE_HTML}</div>`;
  if (!KEYS[name]) { const used = new Set(Object.values(KEYS)); KEYS[name] = [...name.toLowerCase()].find(c => /[a-z]/.test(c) && !used.has(c)); }
});
function loadModule(name) {
  const [ev, w] = MW[name], box = $('module-view');
  box.onclick = e => { const el = e.target.closest('[data-entity]'); if (el) openEntity(el.dataset.entity); else closeSide(); };
  box.onkeydown = e => { const el = e.target.closest('[data-entity]');
    if (el && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openEntity(el.dataset.entity); } };
  frag(`${D.base}/w/${D.state.id}/${ev}/${encodeURIComponent(w)}`).then(h => {
    if (tab !== name) return;
    inject(box, h);
    if (Q.get('ent')) openEntity(Q.get('ent'));
  });
}
function markEntity(id) {  // the open entity looks selected (the rail's look); a style rule survives the module's own redraws
  let st = $('ent-sel');
  if (!st) { if (!id) return; st = document.createElement('style'); st.id = 'ent-sel'; document.head.appendChild(st); }
  const s = id ? `#module-view [data-entity="${CSS.escape(id)}"]` : '';
  st.textContent = id ? `${s}{background:rgb(229 229 229);border-left-color:rgb(23 23 23)} .dark ${s}{background:rgb(38 38 38);border-left-color:rgb(245 245 245)}` : '';
}
function openEntity(id) {
  const el = document.querySelector(`#module-view [data-entity="${CSS.escape(id)}"]`);
  if (!el) { setQ('ent', ''); return; }
  side.id = null; setQ('ev', ''); setQ('ent', id); markEntity(id);
  $('ev-side').classList.remove('hidden');
  $('ev-name').textContent = el.dataset.entityName || id;
  $('ev-sub').textContent = el.dataset.entitySub || '';
  $('ev-tabs').innerHTML = '';
  const parts = [...Object.entries(D.entity_parts || {}), ['JSON', null]], key = p => partKey('entity', p);
  $('ev-body').innerHTML = parts.map(([p]) => partHtml(p, localStorage.getItem(key(p)) !== 'closed')).join('');
  $('ev-body').querySelectorAll('details').forEach(d => d.ontoggle = () =>
    d.open ? localStorage.removeItem(key(d.dataset.part)) : localStorage.setItem(key(d.dataset.part), 'closed'));
  // each part is a project widget for this entity, on the root event (every entity has it); JSON is its events
  parts.forEach(([p, w]) => (w
    ? frag(`${D.base}/w/${encodeURIComponent(id)}/${M().root}/${encodeURIComponent(w)}?task=${encodeURIComponent(id)}`)
        .then(h => `<div data-w-host class="px-4 pt-1">${h}</div>`)
    : fetch(`${D.base}/state.json?task=${encodeURIComponent(id)}`).then(r => r.json()).then(d => jsonPre(d.events || d)))
    .then(html => { if (Q.get('ent') !== id) return;
      const body = $('ev-body').querySelector(`details[data-part="${CSS.escape(p)}"] .part-body`); if (body) inject(body, html); }));
}
let tab = Q.get('tab') || (location.hash ? decodeURIComponent(location.hash.slice(1)) : 'Domain');
if (!(tab in TABS) || !D.tabs.includes(tab)) tab = 'Domain';
function show(name) {
  if (name !== tab) { setQ('ev', ''); setQ('side', ''); setQ('w', ''); setQ('ent', ''); markEntity(null); side.id = null; }
  tab = name; setQ('tab', name === 'Domain' ? '' : name);
  $('mod-name').textContent = Q.get('embed') === 'toolbar' && Q.get('sim_tab') ? Q.get('sim_tab') : tab;  // SIMULADO: an example module
  const wide = GRAPH(tab) || tab === 'Task Results' || isModule(tab);  // full width: no entity rail, no JSON inspector
  $('rail').style.display = $('side').style.display = wide ? 'none' : '';
  $('main').innerHTML = TABS[tab]();
  $('main').querySelectorAll('.rec').forEach(r => r.onclick = () => select(r.dataset.id));
  if (tab === 'Task Results') {
    const slug = D.base.split('/').pop();
    frag(`/domain/tasks/w/_/task.executed/Tasks?domain=${slug}&task=${Q.get('task') || ''}`).then(h => inject($('task-results'), h));
  }
  if (tab === 'Visão' && D.home.length)
    frag(`${D.base}/w/${D.state.id}/${D.home[0]}/${encodeURIComponent(D.home[1])}`).then(h => inject($('home'), h));
  else if (tab === 'Visão') mermaid.run({querySelector: '#main .mermaid'});
  if (GRAPH(tab)) { drawGraph(); $('ev-close').onclick = closeSide; }
  if (isModule(tab)) { loadModule(tab); $('ev-close').onclick = closeSide; }
}
function select(id) {
  document.querySelectorAll('.rec').forEach(r => r.classList.toggle('sel', r.dataset.id === id));
  $('inspector').textContent = JSON.stringify(byId[id], null, 2);
}
// Vim-style goto (like `g t` in vim / `g i` in Gmail): g, then the tab's letter. c toggles the code panel.
let pending = null;
document.addEventListener('keydown', e => {
  if (e.metaKey || e.ctrlKey || e.altKey || /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
  if (pending) {
    clearTimeout(pending); pending = null; $('keyhint').textContent = '';
    const t = Object.keys(KEYS).find(name => KEYS[name] === e.key);
    if (t && t in TABS && D.tabs.includes(t)) { show(t); e.preventDefault(); }
    return;
  }
  if (e.key === 'g') { $('keyhint').textContent = 'g…'; pending = setTimeout(() => { pending = null; $('keyhint').textContent = ''; }, 1200); return; }
  if ((e.key === 'l' || e.key === 'L') && GRAPH(tab) && !popOpen()) { toggleLayout(); e.preventDefault(); return; }
  if (e.key === 'Escape') { popOpen() ? closeWidget() : closeSide(); return; }
  if (popOpen()) return;
});
$('inspector').textContent = JSON.stringify(D.state, null, 2);
if (Q.get('embed') && !['toolbar', 'money'].includes(Q.get('embed'))) $('bar').style.display = 'none';  // ?embed=1: a widget embeds this view, without the status line
show(tab);
if (Q.get('embed')) document.documentElement.dataset.embed = Q.get('embed');
if (Q.get('embed') === 'switcher') domOpen();  // the DomainSwitcher widget: the real switcher, open  // CSS hides what an embed leaves out
if (GRAPH(tab) && Q.get('ev')) {
  const ev = Q.get('ev'), w = Q.get('w');
  openSide(ev);
  if (w) openWidget(ev, w);
}
"""


MONEY_JS = r"""
// The money bar: spent today in the cost center ticks every second while the clock runs; Start / Pause is explicit.
// The clock stops by itself on Pause, another domain's page (the server ends that one), the page hidden, and 5 min
// idle on the Mac (the native app reports it through window.devconsoleIdle; a browser falls back to its own input).
// Never on window blur. Coming back does not restart it. The server is the only writer of the Costs journal.
const $ = id => document.getElementById(id);
const D = JSON.parse($('data').textContent), Q = new URLSearchParams(location.search);
const box = $('money');
// Inside DevConsole.app the window draws the status line natively (chrome); the page keeps the content, so its own
// line is hidden there and pushes the numbers to the app. In a plain browser nothing changes (agents read it headless).
const APP = !!window.webkit?.messageHandlers?.devconsole && !Q.get('embed');
let pushed = '';
const pushStatus = s => {
  if (!APP) return;
  const mod = ($('mod-name') || {}).textContent || (D.name === 'Playground' ? 'Playground' : '');
  const msg = JSON.stringify({type: 'status', domain: D.name, base: D.base, module: mod || null, cost_center: s ? s.name : null,
    running: !!(s && s.running), today_brl: s ? s.spent : null, budget_brl: s && !s.investment ? s.budget : null});
  if (msg !== pushed) { pushed = msg; window.webkit.messageHandlers.devconsole.postMessage(JSON.parse(msg)); }
};
if (APP) {
  const hide = document.createElement('style');
  hide.textContent = '#bar{display:none !important}';
  document.head.appendChild(hide);
  if (!(box && D.money)) { pushStatus(null); setInterval(() => pushStatus(null), 2000); }
}
const EMB = Q.get('embed') === 'money';  // the CostToolbar widget: it shows the bar and the ▶ works on click, but it never enters, beats or stops by itself
if (box && D.money && (!Q.get('embed') || EMB)) {
  let mine = false, S = D.money, t0 = performance.now(), last = Date.now(), leaving = false, native = null, popOpen = false;
  const brl = (v, d = 2) => 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
  const hm = sec => { const m = Math.floor(sec / 60); return Math.floor(m / 60) + 'h' + String(m % 60).padStart(2, '0'); };
  const units = ['min', 'hora', 'dia'];
  const unit = () => { const u = localStorage.getItem('dc.rate'); return units.includes(u) ? u : 'min'; };
  const rateText = () => ({min: brl(S.rate.minute) + '/min', hora: brl(S.rate.hour) + '/h', dia: brl(S.rate.day) + '/dia'})[unit()];
  const live = () => S.running ? S.elapsed + (performance.now() - t0) / 1000 : 0;
  const spentNow = () => S.closed_money + live() * S.rate_hour_running / 3600;
  const secondsNow = () => S.closed_seconds + live();
  const dim = 'text-neutral-400', mute = 'text-neutral-500 dark:text-neutral-400', strong = 'text-neutral-800 dark:text-neutral-200';
  const button = () => `<span data-act="toggle" tabindex="0" aria-label="${S.running ? 'pausar' : 'iniciar'}" title="${S.running ? 'pausar' : 'iniciar'}"
    class="px-1.5 select-none ${strong} hover:text-neutral-500">${S.running ? '⏸' : '▶'}</span>`;
  const name = () => `<span data-act="center" tabindex="0" title="hoje, por centro de custo" class="${mute} hover:text-neutral-900 dark:hover:text-neutral-100">${S.name}</span>`;
  function draw() {
    const spent = spentNow(), secs = secondsNow();
    if (S.investment) {
      box.innerHTML = `${name()}<span class="${dim}">·</span><span class="tabular-nums font-semibold ${strong}">${brl(spent)} hoje</span>
        <span data-act="rate" tabindex="0" title="min · hora · dia" class="tabular-nums ${mute} hover:text-neutral-900">${rateText()}</span>${button()}`;
    } else {
      const over = spent > S.budget, pct = Math.min(100, spent / S.budget * 100);
      const eff = secs > 0 ? S.budget / (secs / 3600) : null;
      box.innerHTML = `${name()}
        <div class="flex flex-col"><div>
          <span class="tabular-nums font-semibold ${over ? 'over' : strong}">${brl(spent)}</span>
          <span class="tabular-nums ${dim}">de ${brl(S.budget)}</span>
          ${over && eff ? `<span class="ml-2 text-[10px]"><span class="over">passou do orçamento</span><span class="${dim}"> · hoje a ${S.name} pagou ${brl(eff, 0)}/h</span></span>` : ''}</div>
          <div class="mt-0.5 h-[2px] bg-neutral-200 dark:bg-neutral-800"><div class="h-full ${over ? 'bg-red-600' : S.running ? 'bg-neutral-800 dark:bg-neutral-200' : 'bg-neutral-400'}" style="width:${pct}%"></div></div></div>
        <span data-act="rate" tabindex="0" title="min · hora · dia" class="tabular-nums ${mute} hover:text-neutral-900">${rateText()}</span>${button()}`;
    }
    if (popOpen) drawPop();
    pushStatus({name: S.name, running: S.running, spent, budget: S.budget, investment: S.investment});
  }
  // the native status line's ▶/⏸ does what the web button does (the page keeps the beat and the idle rules)
  window.devconsoleToggle = () => { if (S.running) stop('pause'); else start(); };
  // the popover: today per cost center and the total (the DayCost numbers); the running stretch counts live
  const pop = document.createElement('div');
  pop.id = 'money-pop';
  pop.className = 'hidden fixed bottom-7 right-0 z-[9999] min-w-[18rem] px-4 py-3 rounded-t-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 shadow-2xl font-sans text-sm';
  document.body.appendChild(pop);
  function drawPop() {
    const rows = S.days.map(d => d.id === S.center ? {...d, seconds: secondsNow(), cost: spentNow()} : d).filter(d => d.seconds > 0 || d.id === S.center);
    const row = (n, sec, cost, bud) => `<div class="grid grid-cols-[8rem_3.5rem_6.5rem_auto] gap-2 py-0.5">
      <span class="${strong}">${n}</span><span class="tabular-nums ${dim}">${hm(sec)}</span>
      <span class="tabular-nums text-right font-semibold ${bud && cost > bud ? 'over' : strong}">${brl(cost)}</span>
      <span class="tabular-nums ${dim}">${bud ? 'de ' + brl(bud) : 'investido'}</span></div>`;
    pop.innerHTML = `<div class="mb-1 text-[11px] uppercase tracking-widest ${mute}">hoje, por centro de custo</div>` +
      rows.map(d => row(d.name, d.seconds, d.cost, d.budget_day)).join('') +
      `<div class="mt-1 pt-1 border-t border-neutral-200 dark:border-neutral-800 grid grid-cols-[8rem_3.5rem_6.5rem_auto] gap-2">
        <span class="${mute}">total</span><span class="tabular-nums ${dim}">${hm(rows.reduce((a, d) => a + d.seconds, 0))}</span>
        <span class="tabular-nums text-right font-semibold ${strong}">${brl(rows.reduce((a, d) => a + d.cost, 0))}</span></div>`;
  }
  const togglePop = open => { popOpen = open ?? !popOpen; pop.classList.toggle('hidden', !popOpen); if (popOpen) drawPop(); };
  // after a start, a stop or an enter the clock may run somewhere else now: a module that draws money (the Kanban's
  // Quadro) listens for devconsole-money on document and redraws at once
  const post = (path, body = {}) => fetch(`${D.base}/time/${path}`, {method: 'POST', body: new URLSearchParams(body)})
    .then(r => r.json()).then(s => { if (s && !s.error) { S = s; t0 = performance.now(); draw(); }
      if (path !== 'beat') document.dispatchEvent(new CustomEvent('devconsole-money', {detail: {path, running: !!(s && s.running)}}));
      return s; }).catch(() => {});
  const stop = (by, trim = 0) => { if (!S.running) return; S.closed_money = spentNow(); S.closed_seconds = secondsNow(); S.running = false; draw(); return post('stop', {ended_by: by, trim_seconds: trim}); };
  const start = () => { entered = true; return post('start').then(() => { last = Date.now(); mine = true; }); };
  const auto = () => !EMB || mine;  // an embed stops, beats and enters only for a stretch its own click started
  const act = el => {
    const a = el && el.closest && el.closest('[data-act]'); if (!a) return;
    if (a.dataset.act === 'rate') { localStorage.setItem('dc.rate', units[(units.indexOf(unit()) + 1) % 3]); draw(); }
    else if (a.dataset.act === 'center') togglePop();
    else if (S.running) stop('pause'); else start();
  };
  box.addEventListener('click', e => act(e.target));
  box.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { act(e.target); e.preventDefault(); } });
  document.addEventListener('click', e => { if (popOpen && !box.contains(e.target) && !pop.contains(e.target)) togglePop(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && popOpen) togglePop(false); });
  let entered = false;  // the first gesture of a person here ends a stretch running in another domain (agents' clicks are not trusted)
  for (const t of ['keydown', 'click', 'scroll', 'pointermove', 'wheel']) addEventListener(t, e => { last = Date.now();
    if (!EMB && !entered && e.isTrusted) { entered = true; post('enter'); } }, {capture: true, passive: true});
  // the native app calls this every 5 s with the seconds since the Mac's last input of any kind
  window.devconsoleIdle = seconds => { native = {seconds, at: Date.now()}; };
  const idleSeconds = () => native ? native.seconds + (Date.now() - native.at) / 1000 : (Date.now() - last) / 1000;
  addEventListener('pagehide', () => { leaving = true; });  // navigating inside the domain or reloading: the server keeps the stretch
  addEventListener('pageshow', e => { leaving = false; if (e.persisted && auto()) post('beat'); });
  // the native app feeds the Mac's idle (devconsoleIdle): there a covered window or a reload behind the chat is not
  // leaving, and only 5 min idle stops; a browser tab still stops when hidden
  const NATIVE = /DevConsole/.test(navigator.userAgent) || !!window.webkit?.messageHandlers?.devconsole;
  document.addEventListener('visibilitychange', () => { if (document.hidden && entered && !leaving && !NATIVE && !native && auto()) stop('hidden'); });  // only a page a person used
  setInterval(() => {
    const idle = idleSeconds();
    if (S.running && auto() && idle > S.idle_minutes * 60) stop('idle', idle);
    else draw();
  }, 1000);
  setInterval(() => { if (S.running && auto()) post('beat'); }, 10000);
  draw();
  // a page load never stops the clock (an agent's or a background tab's load is not a person leaving)
}
"""


title_of = PROJECT.title_of


@rt("/domain/{slug}/source/stream")
async def source_stream(slug: str):
    """Server-sent events: the real model again whenever the domain's SOURCE changes on disk."""
    import asyncio

    from starlette.responses import StreamingResponse

    async def gen():
        use(slug)
        last = None
        while True:
            m = (SOURCE.stat().st_mtime, draft_path().stat().st_mtime if draft_path().exists() else 0)
            if m != last:
                last = m
                yield f"data: {json.dumps(real_model(), ensure_ascii=False)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- Agents: what the owner typed to the agents, and the agents' logs, in real time (the logic is console_agents.py) -----
sys.path.insert(0, str(Path(__file__).resolve().parent))
import console_agents as AG  # noqa: E402

try:  # the server stops the tailer thread on shutdown (a reload kills the child process anyway)
    app.router.on_shutdown.append(AG.stop_hub)
except AttributeError:
    pass


def _agents_args(limit: int, session: str, side: str) -> dict:
    return {"limit": limit, "session": session, "side": side in ("1", "true")}


@rt("/agents/api/prompts")
def agents_prompts(limit: int = 200, session: str = "", kinds: str = "prompt", side: str = ""):
    return _json(AG.ready_hub().get_prompts(kinds=[k for k in kinds.split(",") if k], **_agents_args(limit, session, side)))


@rt("/agents/api/log")
def agents_log(limit: int = 500, session: str = "", side: str = ""):
    return _json(AG.ready_hub().get_log(**_agents_args(limit, session, side)))


@rt("/agents/api/entry")
def agents_entry(id: str = ""):
    e = AG.ready_hub().get_entry(id)
    return _json(e or {"error": "unknown entry"}, 200 if e else 404)


@rt("/agents/events")
async def agents_events(req, after: str = ""):
    """SSE, one stream per client over the one tailer; resumes from Last-Event-ID (header) or ?after=."""
    from starlette.responses import StreamingResponse

    hub = await asyncio.to_thread(AG.ready_hub)
    return StreamingResponse(AG.sse(hub, req.headers.get("last-event-id") or after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@rt("/agents")
def agents_page():
    """The Agents module: the console's bar and, above it, two live views (Prompts, Log) of the agents' session logs."""
    domains = [{"slug": s, "name": m.NAME, "entity": getattr(m, "ENTITY", "")} for s, m in DOMAINS.items()]
    payload = json.dumps({"base": f"/domain/{PLAYGROUND_SLUG}", "name": "Agents", "domains": domains, "modules": _modules()},
                         ensure_ascii=False).replace("</", "<\\/")
    btn = "px-2 rounded border border-transparent cursor-pointer"
    chip = lambda k: Span(k, id=f"c-{k}", tabindex="0", cls=btn)  # spans without role="button": MonsterUI paints <button> and role="button" as blue filled buttons  # noqa: E731
    tools = Div(
        Span("Prompts", id="v-prompts", tabindex="0", cls="px-2 cursor-pointer"), Span("Log", id="v-log", tabindex="0", cls="px-2 cursor-pointer"),
        NotStr('<select id="sess" class="h-6 max-w-[28rem] bg-transparent border border-neutral-300 dark:border-neutral-700 rounded px-1"></select>'),
        chip("cross"), chip("notification"), chip("other"), chip("side"),
        Span("", id="pause", tabindex="0", cls="ml-auto px-2 cursor-pointer whitespace-nowrap"), Span("", id="live", cls="whitespace-nowrap"),
        cls="h-9 shrink-0 flex items-center gap-2 px-3 border-b border-neutral-200 dark:border-neutral-800 text-neutral-500")
    # the module's own script reuses the Playground's preamble + the one switcher script, with ⌘P's current module set
    pre = PLAYGROUND_JS.replace("'/playground'", "'/agents'")  # the Playground's script is exactly preamble + switcher
    return Title("dev-console · Agents"), Link(rel="icon", href="data:,"), Style(CSS), Div(
        tools, Div(id="warn", cls="px-3 text-amber-600 empty:hidden"), Div(id="aglist", cls="flex-1 min-h-0 overflow-y-auto"),
        _status_bar("Agents", False, module=False), _switcher(),
        Script(payload, type="application/json", id="data"), Script(pre + AG.AGENTS_JS, type="module"),
        cls="h-screen flex flex-col font-mono text-xs bg-white dark:bg-neutral-950",
    )


# --- the money bar: the Costs domain's journal is the only storage (cost-track's costs.py is its only writer) --------
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
    if run and (_now() - datetime.fromisoformat(run["last_seen"])).total_seconds() > STALE_SECONDS:
        _close_run("close", now=datetime.fromisoformat(run["last_seen"]))


def _leave(slug: str):
    """A page of another domain opened: a stretch running elsewhere ends (domain_change)."""
    _settle()
    run = C.running() if C else None
    if run and run["domain"] != slug:
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


def _json(data, status: int = 200):
    from starlette.responses import JSONResponse

    return JSONResponse(data, status_code=status)


@rt("/domain/{slug}/time")
def time_state(slug: str):
    """Today's numbers for the domain's bar (read only)."""
    if not _known(slug):
        return _json({"error": "no such domain"}, 404)
    _settle() if C else None
    state = _money_state(slug)
    return _json(state or {"error": "no cost center"}, 200 if state else 404)


@rt("/api/status")
def api_status(domain: str = ""):
    """Read-only, for the native status line's slow refresh: {domain, cost_center, running, today_brl, budget_brl, module}.
    `today_brl` counts the running stretch up to now. `module` is null: only the page knows its tab (it pushes it)."""
    if not domain or not _known(domain):
        return _json({"error": "no such domain"}, 404)
    _settle() if C else None
    m = _money_state(domain)
    if not m:
        return _json({"domain": domain, "cost_center": None, "running": False, "today_brl": None, "budget_brl": None, "module": None})
    spent = m["closed_money"] + m["elapsed"] * m["rate_hour_running"] / 3600
    return _json({"domain": domain, "cost_center": m["name"], "running": m["running"], "today_brl": round(spent, 2),
                  "budget_brl": None if m["investment"] else m["budget"], "module": None})


@rt("/domain/{slug}/time/enter", methods=["POST"])
def time_enter(slug: str):
    """A person acted on this domain's page (a trusted gesture): a stretch running in another domain ends."""
    if not _known(slug):
        return _json({"error": "no such domain"}, 404)
    if C:
        _leave(slug)
    return _json(_money_state(slug) or {"error": "no cost center"})


@rt("/domain/{slug}/time/start", methods=["POST"])
def time_start(slug: str):
    """Start a stretch (the only way the clock runs); one at a time, another domain's ends first (domain_change)."""
    if not _known(slug):
        return _json({"error": "no such domain"}, 404)
    center = _center_of(slug)
    rate = C.rate_hour(center) if center else None
    if not rate:
        return _json({"error": "no cost center"}, 404)
    _settle()
    run = C.running()
    if not (run and run["domain"] == slug and run["center"] == center):
        if run:
            _close_run("domain_change")
        now = _now().isoformat(timespec="seconds")
        C.emit("time_entry.started", {"text": C.started_text(center, slug), "domain": slug}, cost_center=center, actor="dev-console")
        C.set_running({"center": center, "domain": slug, "started_at": now, "last_seen": now, "rate_hour": rate})
    return _json(_money_state(slug))


@rt("/domain/{slug}/time/beat", methods=["POST"])
def time_beat(slug: str):
    """The page is alive: a stretch nobody pings for a while is closed (ended_by close)."""
    if not _known(slug):
        return _json({"error": "no such domain"}, 404)
    if C:
        _settle()
        run = C.running()
        if run:
            C.set_running({**run, "last_seen": _now().isoformat(timespec="seconds")})
    return _json(_money_state(slug) or {"error": "no cost center"})


@rt("/domain/{slug}/time/stop", methods=["POST"])
def time_stop(slug: str, ended_by: str = "pause", trim_seconds: float = 0):
    """End the running stretch (pause | domain_change | hidden | idle | close); idempotent."""
    if not _known(slug):
        return _json({"error": "no such domain"}, 404)
    if C:
        _close_run(ended_by, trim=min(max(trim_seconds, 0), 86400))
    return _json(_money_state(slug) or {"error": "no cost center"})


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


@rt("/domain/{slug}/do/{eid}/{name}")
def do_action(slug: str, eid: str, name: str, mode: str = "real", step: int = 0):
    """Run a project action on one event (PROJECT.ACTIONS[name](event, mode, step)): the only write path, and it is
    the project's. mode=sim plays the experience without writing or sending anything; step walks its stages."""
    if not use(slug):
        return P(f"domínio {slug} não existe", cls="text-neutral-500")
    fn = getattr(PROJECT, "ACTIONS", {}).get(name)
    ev = next((e for e in journal.read({"history": True}) if e["id"] == eid), None)
    if not fn or not ev:
        return P(f"ação {name} ou evento {eid[:8]} não existe", cls="text-neutral-500")
    return fn(ev, mode="sim" if mode == "sim" else "real", step=step)


@rt("/domain/{slug}/w/{tid}/{event}/{name}")
def one_widget(slug: str, tid: str, event: str, name: str, e: str = "", mode: str = "real", domain: str = "", task: str = ""):
    """One widget, rendered for the popup (mode=sim: simulated, nothing is written). ?task=<entity> picks that
    entity's last event of this type; ?domain=<slug> says which domain the screen is about."""
    if not use(slug):
        return _empty(f"domínio {slug} não existe")
    if domain and not task and not e:  # no pick yet: the newest entity of that domain that has this event
        mine = {t["id"] for t in journal.read() if t.get("domain") == domain}
        own = [x for x in journal.read({"event": event}) if x[entity_key()] in mine]
        e = own[-1]["id"] if own else ""
    if task and not e:
        own = [x for x in journal.read({"id": task, "history": True}) if x["event"] == event]
        e = own[-1]["id"] if own else ""
    return W.render_one(_ctx(tid, event, e or None, "sim" if mode == "sim" else "real", domain), name)


@rt("/domain/{slug}/media")
def media(slug: str, f: str = ""):
    """A file the domain keeps with its records (MEDIA in the project file: pictures of a run), never outside it.
    The path goes in ?f=, because FastHTML's own static route takes any URL ending in .png first."""
    path = f
    from starlette.responses import FileResponse, Response

    mod = use(slug)  # the registry's domains too, not only the --project ones
    root = Path(getattr(mod, "MEDIA", "") or "/nonexistent").expanduser().resolve()
    file = (root / path).resolve()
    if mod is None or root not in file.parents or not file.is_file():
        return Response("não encontrado", status_code=404)
    return FileResponse(file)


@rt("/domain/{slug}/w/{tid}/{event}")
def event_widgets(slug: str, tid: str, event: str, e: str = ""):
    """The list of widgets the project registers for an event, each with its open action."""
    if not use(slug):
        return _empty(f"domínio {slug} não existe")
    return W.render_list(_ctx(tid, event, e or None))


@rt("/")
def index():
    """The console's home: the module a domain names with CONSOLE_HOME (the Kanban's Quadro), when that domain has an
    entity to open; else the first domain, as before. The status line switches between them."""
    for slug, mod in DOMAINS.items():
        home = getattr(mod, "CONSOLE_HOME", None)
        if not home or not use(slug):
            continue
        try:
            has_entity = bool(journal.read())
        except Exception:  # a broken journal must not take the home down: the first domain opens instead
            has_entity = False
        if has_entity:
            return RedirectResponse(f"/domain/{slug}?tab={quote(home)}", status_code=303)
    return RedirectResponse(f"/domain/{_first_domain()}", status_code=303)


def _first_domain() -> str:
    """The first domain of this console (its first --project, else the registry's first line)."""
    return next(iter(DOMAINS))


@rt("/domain/{slug}")
def domain(slug: str, req):
    if slug == PLAYGROUND_SLUG and slug not in DOMAINS:
        return RedirectResponse("/playground", status_code=303)
    if not use(slug):
        return Title("não encontrado"), Div(f"Domínio {slug} não existe. Há: {', '.join(DOMAINS)}.", cls="p-8 font-mono text-sm")
    entities = journal.read()
    if not entities:
        return Title(PROJECT.NAME), Div(f"Nenhum(a) {PROJECT.ENTITY} no diário.", cls="p-8 font-mono text-sm")
    q = f"?{req.url.query}" if req.url.query else ""  # keep the view (?tab=…&ev=…) across the redirect
    return RedirectResponse(f"/domain/{slug}/t/{_default_entity()}{q}", status_code=303)


def _tabs() -> list[str]:
    """The current domain's modules shown in place: Domain and Task Results are fixed (Task Results when the tasks domain
    is in the console), then the context's TABS. The current domain must already be set (use(slug))."""
    fixed = ["Domain", *(["Task Results"] if "tasks" in DOMAINS else [])]
    return [*fixed, *[t for t in getattr(PROJECT, "TABS", []) if t not in fixed]]


def _page_data(slug: str, tid: str, money=None):
    """What a domain page embeds as <script id="data">, as a dict (None when the entity is unknown). The page and
    GET /domain/<slug>/state.json share it, so an agent reads exactly what the screen is drawn from. The current
    domain must already be set (use(slug)); `money` is the page's own bar and is left out of the API."""
    base = PROJECT.BASE
    state = journal.read({"id": tid})
    if not state:
        return None
    history = journal.read({"id": tid, "history": True})
    journal_types: dict[str, int] = {}
    for e in journal.read({"history": True}):
        journal_types[e["event"]] = journal_types.get(e["event"], 0) + 1
    # Domain and Task Results are fixed (Task Results when the tasks domain is in the console); TABS is the context's
    tabs = _tabs()
    domains = [{"slug": s, "name": m.NAME, "entity": getattr(m, "ENTITY", "")} for s, m in DOMAINS.items()]
    # a module drawn by a project widget ({module: [event, widget]}, only the ones in TABS) and the parts of an entity's
    # sidebar ({part title: widget}): see the project contract
    module_widgets = {n: list(v) for n, v in dict(getattr(PROJECT, "MODULE_WIDGETS", None) or {}).items() if n in tabs}
    return {"money": money, "base": base, "name": PROJECT.NAME, "tabs": tabs, "modules": _modules(tabs), "domains": domains, "journal_types": journal_types, "events": history, "state": state, "model": real_model(), "entities": PROJECT.ENTITIES, "home": list(getattr(PROJECT, "HOME", ())),
            "module_widgets": module_widgets, "entity_parts": dict(getattr(PROJECT, "ENTITY_PARTS", None) or {})}


def _default_entity() -> str | None:
    """The entity the domain's own page opens: the newest open one, else the last."""
    entities = journal.read()
    return next((t["id"] for t in reversed(entities) if t.get("status") == "open"), entities[-1]["id"]) if entities else None


@rt("/api/domains")
def api_domains():
    """Every domain this instance shows, for agents: slug, name, project file, and where it came from."""
    return _json([{"slug": s, "name": m.NAME, "path": str(Path(m.__file__).resolve()), "origin": ORIGIN[s]}
                  for s, m in DOMAINS.items()])


@rt("/api/palette")
def api_palette(domain: str = ""):
    """What the native command palette (DevConsole.app, ⌘K / ⌘P) lists, read only: `domains` (slug, name) and `modules`
    (id, title, url). Module urls are paths on this console: the domain's tabs as `/domain/<slug>?tab=<name>` (given
    `?domain=<slug>`), then Playground and Agents; without a domain, Domain (the first one) and those two."""
    domains = [{"slug": s, "name": m.NAME} for s, m in DOMAINS.items()]
    if domain and use(domain):
        modules = [{"id": t, "title": t, "url": f"/domain/{domain}?tab={quote(t)}"} for t in _tabs()]
    else:  # the first domain, as "/" used to open (the home may be another domain's module now)
        modules = [{"id": "Domain", "title": "Domain", "url": f"/domain/{_first_domain()}"}]
    modules += [{"id": "playground", "title": "Playground", "url": "/playground"},
                {"id": AGENTS_MODULE["name"].lower(), "title": AGENTS_MODULE["name"], "url": AGENTS_MODULE["href"]}]
    return _json({"domains": domains, "modules": modules})


import console_recorder as REC  # noqa: E402  (the agent API: /agent/now, /agent/history, /agent/shot; read only)

REC.register(rt, _json)


@rt("/api/domains/{slug}/actions")
def api_actions(slug: str):
    """The names in PROJECT.ACTIONS (the write path, /domain/<slug>/do/<eid>/<name>) of one domain."""
    if not use(slug):
        return _json({"error": f"domain {slug} does not exist"}, 404)
    return _json(sorted(getattr(PROJECT, "ACTIONS", {})))


@rt("/domain/{slug}/state.json")
def state_json(slug: str, task: str = ""):
    """The page's data as JSON (?task=<entity id>, default the entity the page opens)."""
    if not use(slug):
        return _json({"error": f"domain {slug} does not exist", "domains": list(DOMAINS)}, 404)
    data = _page_data(slug, task or _default_entity() or "")
    return _json(data if data else {"error": "no such entity (or an empty journal)"}, 200 if data else 404)


@rt("/domain/{slug}/t/{tid}")
def tension(slug: str, tid: str, embed: str = ""):
    if not use(slug):
        return RedirectResponse("/", status_code=303)
    money = None
    if C and embed in ("", "money"):  # an embed (a widget's iframe) neither runs the clock nor ends another domain's stretch; ?embed=money only shows the bar
        try:  # the money bar is a bonus: it never breaks the page (loading it never ends a stretch: a gesture does)
            money = _money_state(slug)
        except Exception:
            money = None
    base = PROJECT.BASE
    data = _page_data(slug, tid, money)
    if not data:
        return Title("não encontrado"), Div(f"{PROJECT.ENTITY} não encontrado(a).", cls="p-8 font-mono text-sm")
    state, history = data["state"], data["events"]
    title = title_of(history, state)
    ctx = state.get("context") or {}

    rail = []
    for t in sorted(journal.read(), key=lambda s: (s.get("status") != "open", s.get("updated_at", ""))):  # a domain's entity may lack these
        on = t["id"] == tid
        rail.append(Div(
            Div(title_of(journal.read({"id": t["id"], "history": True}), t),
                cls="truncate " + ("font-semibold text-neutral-900 dark:text-neutral-100" if on else "text-neutral-600 dark:text-neutral-400")),
            Div(" · ".join(x for x in (str(t.get("status", "")), f"{t['event_count']} eventos" if "event_count" in t else "") if x),
                cls="text-neutral-400"),
            onclick=f"location.href='{base}/t/{t['id']}'" + "+location.search",
            cls="px-4 py-2 cursor-pointer border-l-2 " + (
                "border-neutral-900 dark:border-neutral-100 bg-neutral-100 dark:bg-neutral-900" if on
                else "border-transparent hover:bg-neutral-100 dark:hover:bg-neutral-900"),
        ))

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    sub = " · ".join(str(ctx[k]) for k in ("project", "version") if k in ctx)
    head = "px-4 pt-3 pb-1 text-[11px] uppercase tracking-widest text-neutral-500"
    line = "border-neutral-200 dark:border-neutral-800"
    bar = _status_bar(PROJECT.NAME, bool(money))
    return Title(f"dev-console · {title}"), Link(rel="icon", href="data:,"), Style(CSS), Div(
        Div(
            Div(Div(PROJECT.ENTITY_PLURAL, cls=head), *rail, id="rail", cls=f"w-56 shrink-0 overflow-y-auto border-r {line}"),
            Div(id="main", cls="flex-1 min-w-0 min-h-0 overflow-y-auto"),
            Div(Div("inspector", cls=head),
                Div(id="inspector", cls="px-4 pb-4 whitespace-pre-wrap break-words text-neutral-600 dark:text-neutral-400"),
                id="side", cls=f"w-80 shrink-0 overflow-y-auto border-l {line}"),
            id="work", cls="flex-1 min-h-0 flex",
        ),
        bar,
        Div(
            Div(
                Div(Div(Div(id="pop-name", cls="font-sans text-lg font-semibold text-neutral-900 dark:text-neutral-100"),
                        Div(id="pop-sub", cls="text-neutral-400"), cls="min-w-0"),
                    Div(Span("REAL", data_mode="real", cls="mode px-2.5 h-7 leading-7 cursor-pointer select-none"),
                        Span("SIMULADO", data_mode="sim", cls="mode px-2.5 h-7 leading-7 cursor-pointer select-none"),
                        id="pop-mode", title="SIMULADO: os botões funcionam, nada é gravado nem enviado",
                        cls="ml-auto mr-3 shrink-0 flex rounded border border-neutral-300 dark:border-neutral-700 text-[11px] tracking-widest"),
                    Div("✕", id="pop-close", title="Esc", cls="shrink-0 px-2 cursor-pointer text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100"),
                    cls="shrink-0 flex items-start justify-between gap-4 px-6 pt-5 pb-3 border-b border-neutral-200 dark:border-neutral-800"),
                Div(id="pop-body", cls="flex-1 min-h-0 overflow-y-auto px-6 py-5"),
                cls="w-[min(860px,92vw)] max-h-[82vh] flex flex-col rounded-lg border border-neutral-300 dark:border-neutral-700 "
                    "bg-white dark:bg-neutral-950 shadow-2xl",
            ),
            id="pop", cls="hidden fixed inset-0 z-[10000] items-center justify-center bg-black/40 backdrop-blur-[1px]",
        ),
        # Domain Switcher: a fuzzy finder (fzf, the editors' command palette) over an overlay
        _switcher(),
        Script(payload, type="application/json", id="data"),
        Script(src="https://cdn.jsdelivr.net/npm/cytoscape@3/dist/cytoscape.min.js"),
        # fCoSE (Balci & Dogrusoz 2022): force-directed with constraints; the Human is pinned in the centre
        Script(src="https://cdn.jsdelivr.net/npm/layout-base@2.0.1/layout-base.js"),
        Script(src="https://cdn.jsdelivr.net/npm/cose-base@2.2.0/cose-base.js"),
        Script(src="https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.js"),
        Script(JS, type="module"),
        Script(MONEY_JS, type="module"),
        cls="h-screen flex flex-col font-mono text-xs bg-white dark:bg-neutral-950",
    )

# --- the Playground: a mode beside Domain, not tied to any domain. The design-playground's canvas lives here now:
# its web is in playground/ (served same-origin, no iframe, so ⌘K and ⌘P reach this page even with the canvas focused)
# and its data and API are console_playground.py. No chat: the agent works the canvas through console.sh -----------
PLAYGROUND_SLUG = "playground"
PLAYGROUND_COST_CENTER = os.environ.get("DEV_CONSOLE_PLAYGROUND_COST_CENTER", "biliboss-skills")  # its time is counted too


def _known(slug: str) -> bool:
    """A domain, or the Playground (the money routes answer for both)."""
    return bool(use(slug)) or (slug == PLAYGROUND_SLUG and slug not in DOMAINS)


AGENTS_MODULE = {"name": "Agents", "href": "/agents"}  # listed by ⌘P beside Domain and Playground


def _modules(tabs: list[str] | None = None) -> list[dict]:
    """The one module model both pages ship as D.modules, listed by ⌘P: `{name, href}`. On a domain page: Domain and the
    project's TABS (href null: shown in place), then Playground (href: navigates). On the Playground: Domain (the first
    domain, where "/" used to go; "/" is the home now) and Playground. ⌘K never lists these: it lists domains only."""
    if tabs is None:
        return [{"name": "Domain", "href": f"/domain/{_first_domain()}"}, {"name": "Playground", "href": "/playground"}, AGENTS_MODULE]
    return [*({"name": n, "href": None} for n in tabs), {"name": "Playground", "href": "/playground"}, AGENTS_MODULE]


def _status_bar(name: str, money: bool, module: bool = True):
    """The status line at the bottom of both pages (VS Code, vim): the name (click = ⌘K), · module (click = ⌘P; the page's JS
    fills #mod-name), the money bar, a faint hint on the right. One markup, so the two pages cannot drift."""
    line = "border-neutral-200 dark:border-neutral-800"
    return Div(
        Span(name, id="dom-open", data_ov="domain", title="trocar de domínio (⌘K)",
             cls="shrink-0 pl-3 pr-1 max-w-[16rem] truncate font-semibold text-neutral-800 dark:text-neutral-200"),
        *([Span(Span("·", cls="mr-1 text-neutral-400"), Span(id="mod-name"),
                id="mod-open", data_ov="module", title="trocar de módulo (⌘P)",
                cls="shrink-0 px-1 text-neutral-500")] if module else []),
        Div(id="keyhint", cls="shrink-0 w-8 text-neutral-400"),
        *([Div(id="money", cls=f"shrink-0 h-full flex items-center gap-3 px-3 whitespace-nowrap border-l {line}")] if money else []),
        Div("⌘K domínio · ⌘P módulo", cls="ml-auto shrink-0 pr-3 whitespace-nowrap text-neutral-300 dark:text-neutral-700"),
        id="bar", cls=f"h-7 shrink-0 flex items-center border-t {line} text-neutral-500",
    )


def _switcher():
    """The Domain Switcher overlay: a fuzzy finder (fzf, the editors' command palette) over a dim layer."""
    return Div(
        Div(NotStr('<input id="dom-q" autocomplete="off" spellcheck="false" placeholder="domínio…" '
                   'class="w-full h-11 px-4 bg-transparent border-0 border-b border-neutral-200 dark:border-neutral-800 '
                   'font-mono text-sm text-neutral-900 dark:text-neutral-100 outline-none">'),
            Div(id="dom-list", cls="max-h-[50vh] overflow-y-auto py-1"),
            Div("↑↓ escolher · Enter abrir · Esc fechar", cls="px-4 h-8 leading-8 border-t border-neutral-200 dark:border-neutral-800 text-neutral-400"),
            cls="w-[min(560px,92vw)] rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 shadow-2xl"),
        id="dom", cls="hidden fixed inset-0 z-[10001] items-start justify-center pt-[16vh] bg-black/40 backdrop-blur-[1px]",
    )


# the switcher script is the main page's own, cut out of JS (one copy), plus the three names it needs
SWITCHER_JS = JS[JS.index("// --- Switcher overlay"):JS.index("function wireRows")]
PLAYGROUND_JS = (r"""
const $ = id => document.getElementById(id);
const D = JSON.parse($('data').textContent), Q = new URLSearchParams(location.search);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
D.module = '/playground';  // the current module, for ⌘P's "· atual"
let tab = '';
const COUNT = {}, KEYS = {};  // the switcher's tags exist on a domain page only
const show = () => {};  // a module with no href is a tab: the Playground has none
""" + SWITCHER_JS)


sys.path.insert(0, str(Path(__file__).resolve().parent))
import console_playground as PG  # noqa: E402  (a sibling file: this script's folder is on sys.path)

PLAYGROUND = PG.Playground()
PG.mount(app, PLAYGROUND)  # /playground/api/*, /playground/web/*: in front of FastHTML's static route


@rt("/playground")
def playground():
    """The Playground: the canvas (same origin) filling the page above the console's status line."""
    money = None
    if C:
        try:  # the money bar is a bonus: it never breaks the page
            money = _money_state(PLAYGROUND_SLUG)  # loading never ends a stretch: the first trusted gesture does (time_enter)
        except Exception:
            money = None
    domains = [{"slug": s, "name": m.NAME, "entity": getattr(m, "ENTITY", "")} for s, m in DOMAINS.items()]
    payload = json.dumps({"money": money, "base": f"/domain/{PLAYGROUND_SLUG}", "name": "Playground", "domains": domains,
                          "modules": _modules()}, ensure_ascii=False).replace("</", "<\\/")
    return Title("dev-console · Playground"), Style(CSS), \
        Link(rel="icon", href="data:,"), Link(rel="stylesheet", href="https://unpkg.com/tldraw@3.15.4/tldraw.css"), \
        Link(rel="stylesheet", href=f"{PG.PREFIX}/web/app.css"), Div(
        Div(id="canvas", cls="flex-1 min-h-0"),
        _status_bar("Playground", bool(money), module=False),
        _switcher(),
        Script(payload, type="application/json", id="data"),
        Script(PLAYGROUND_JS, type="module"),
        Script(MONEY_JS, type="module"),
        Script(src=f"{PG.PREFIX}/web/canvas.js", type="module"),
        Script(src=f"{PG.PREFIX}/web/eventos.js", type="module"),
        cls="h-screen flex flex-col font-mono text-xs bg-white dark:bg-neutral-950",
    )


def _serve(port: int) -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dev-console for an event-sourced project")
    parser.add_argument("--project", action="append", help="path to a dev_console_project.py (repeat: one domain each)")
    parser.add_argument("--port", type=int, default=5057)
    parser.add_argument("--no-live", action="store_true", help="never reload the open pages on a save (second instance)")
    args = parser.parse_args()
    projects = [Path(p).resolve() for p in dict.fromkeys((args.project or []) + os.environ.get("DEV_CONSOLE_PROJECT", "").split(os.pathsep)) if p]
    if not projects:
        parser.error("--project is required (or DEV_CONSOLE_PROJECT)")
    os.environ["DEV_CONSOLE_PROJECT"] = os.pathsep.join(map(str, projects))
    from watchfiles import run_process

    # Hot reload: restart on any change in this file or a project folder; live=True reloads the page.
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)

    def _registry_changed(changes) -> None:  # a new domain: re-exec, so the watcher also watches its folder
        if any(Path(p) == REGISTRY for _, p in changes) and set(registered()) - {str(p) for p in projects}:
            import multiprocessing

            for child in multiprocessing.active_children():  # free the port before the new watcher starts its server
                child.terminate()
                child.join(5)
            os.execv(sys.executable, [sys.executable, *sys.argv])

    run_process(Path(__file__).parent, REGISTRY.parent, *{p.parent for p in projects}, target=_serve, args=(args.port,),
                callback=_registry_changed)
