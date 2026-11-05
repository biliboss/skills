# /// script
# requires-python = ">=3.10"
# dependencies = ["python-fasthtml>=0.14", "monsterui>=1.0.48"]
# ///
"""dev-console: a read-only, full-screen console for an event-sourced project in development (FastHTML + MonsterUI).

Run:  uv run --script dev-console.py --project <a/dev_console_project.py> [--project <b/...>] [--port 5057]
Each project file is one domain, served in its own context at /domain/<slug> (SLUG, else the skill folder name).
A project file says what to show (see the skill's references/project-contract.md):
  NAME, SOURCE (file with the EVENTS registry {category: {command: event}}), ENTITY, ENTITY_PLURAL,
  ENTITIES ({category: entity name}), PROJECTOR (the fold function), journal (.read(query)), title_of(), WIDGETS.
Layout: tabs first; the entity rail on the left; the selected record on the right. Domain (first tab) = the
domain model (DDD: aggregate root, entities, commands, events); Model = the state machine.
Keys (vim-style goto): g d Domain, g m Model, g v Visão, g p Proposed Actions, g o Observations, g r Relationships,
g t Management, g e Eventos, g y Tipos; Esc closes the popup, then the sidebar. All UI state lives in the query.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import importlib.util  # noqa: E402
import os  # noqa: E402
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
for _path in os.environ["DEV_CONSOLE_PROJECT"].split(os.pathsep):
    _mod = load_project(_path)
    _slug = getattr(_mod, "SLUG", None) or Path(_path).resolve().parent.parent.name
    _mod.SLUG, _mod.BASE = _slug, f"/domain/{_slug}"  # BASE: the domain's URL prefix (actions build links with it)
    DOMAINS[_slug] = _mod
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
from fasthtml.common import A, Div, Li, NotStr, P, Script, Span, Style, Title, Ul, fast_app  # noqa: E402
from monsterui.all import Theme  # noqa: E402
from starlette.responses import RedirectResponse  # noqa: E402

app, rt = fast_app(hdrs=Theme.neutral.headers(mode="auto"), live=True)  # live: the browser reloads on save
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
            "coverage": W.coverage(live_events()), "descriptions": descriptions(), "value_objects": value_objects(), **derive(live_events(), getattr(PROJECT, "INITIAL", None), getattr(PROJECT, "HUB", None),
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


for _mod in DOMAINS.values():
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
html[data-embed=switcher] #bar, html[data-embed=switcher] #bar ~ :not(#dom) { visibility: hidden; }
html[data-embed=switcher] #dom { padding-top: 24px; }
/* ?embed=toolbar: the real tab bar alone (Toolbar widget) */
html[data-embed=toolbar] #bar ~ * { display: none !important; }
html[data-embed=toolbar] #bar { border-bottom: 0; }
.tab.on{color:rgb(23 23 23);border-color:rgb(23 23 23)} .dark .tab.on{color:rgb(245 245 245);border-color:rgb(245 245 245)}
.rec.sel{background:rgb(229 229 229)} .dark .rec.sel{background:rgb(38 38 38)}
.mermaid svg{max-width:100%}
/* the right menu's expandable parts: no Pico margins, the chevron right after the title */
#ev-body details { margin: 0; padding: 0; } #ev-body details summary { margin: 0; list-style: none; }
#ev-body details summary::after { float: none; margin-left: .25rem; }
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

function drawGraph() {
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
  const cy = cytoscape({
    container: $('cy'), elements: {nodes, edges}, wheelSensitivity: 0.2,
    // fCoSE: force-directed, the Human pinned in the centre; seeded (randomize false + fixed seed positions) so a
    // reload draws the same picture. nodeRepulsion and idealEdgeLength leave room for the edge labels.
    layout: {name: 'fcose', quality: 'proof', randomize: false, animate: false, padding: 24,
             nodeDimensionsIncludeLabels: true, idealEdgeLength: () => 130, nodeRepulsion: () => 45000,
             edgeElasticity: () => 0.45, gravity: 0.4, gravityRange: 2.5, numIter: 5000, nodeSeparation: 90,
             fixedNodeConstraint: [{nodeId: 'human', position: {x: 0, y: 0}}],
             // the starts sit in line with the Human, one on each side; what follows them hangs below
             ...(STARTS.length > 1 ? {alignmentConstraint: {horizontal: [['human', ...STARTS]]},
               relativePlacementConstraint: [{left: STARTS[0], right: 'human', gap: 160}, {left: 'human', right: STARTS[1], gap: 160},
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
      {selector: 'node.human', style: {shape: 'ellipse', width: 34, height: 34, 'background-color': ink,
        'border-width': 0, color: ink, 'font-size': 15, 'font-weight': 700, 'text-valign': 'bottom', 'text-margin-y': 8,
        'font-family': 'ui-sans-serif, system-ui'}},
      {selector: 'edge', style: {label: 'data(label)', 'font-family': 'ui-monospace, monospace', 'font-size': 15,
        color: 'data(color)', 'text-background-color': bg, 'text-background-opacity': 1, 'text-background-padding': '3px',
        'text-rotation': 'autorotate'}},
      {selector: 'edge', style: {width: 2, 'line-color': 'data(color)', 'target-arrow-color': 'data(color)',
        'target-arrow-shape': 'triangle', 'arrow-scale': 0.8, 'curve-style': 'straight', 'line-opacity': 0.45}},
      {selector: 'edge.walked', style: {width: 3.5, 'line-opacity': 1}},
      // a loop (A -> B and B -> A, from TRANSITIONS): two curved edges, side by side, so neither hides the other
      {selector: 'edge.loop', style: {'curve-style': 'bezier', 'control-point-step-size': 60}},
      {selector: ':selected', style: {'border-width': 4, 'border-color': ink, 'border-opacity': 1}},
    ],
  });
  let box = '';
  new ResizeObserver(([e]) => {
    const k = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;
    if (k === box || !e.contentRect.width) return;  // same size: do nothing (this guard stops the flicker loop)
    box = k; cy.resize(); cy.fit(undefined, 20);
  }).observe($('cy'));
  $('legend').innerHTML = Object.entries(PATH).filter(([c]) => c in M().lifecycle).map(([c, col]) => `<span style="color:${col}">● ${c}</span>`).join('')
    + '<span>· aresta: comando (transição) · nó: evento (estado alcançado) · cheio: já no diário</span>';
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
  'JSON': id => Promise.resolve(`<pre class="m-0 p-4 !bg-transparent whitespace-pre-wrap text-neutral-600 dark:text-neutral-400">${esc(JSON.stringify(E.filter(e => e.event === id), null, 2))}</pre>`),
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
  $('ev-sub').textContent = `comando ${M().commands[id]} · ${n} ${n === 1 ? 'evento' : 'eventos'} · ${w.length ? w.join(', ') : 'sem widgets'}`;
  renderSide();
}
// The right menu is a column of expandable parts (Widgets only when the event has widgets; Code, JSON, and
// Observability last, since every event has it). Every part starts open; each node remembers which parts the user
// closed, in localStorage (key per domain, event and part).
const sideParts = id => Object.keys(SIDE_TABS).filter(t => t !== 'Widgets' || ((M().coverage || {})[id] || []).length);
const partKey = (id, p) => `dev-console:part:${D.base}:${id}:${p}`;
function renderSide() {
  const want = side.id, parts = sideParts(want);
  $('ev-tabs').innerHTML = '';
  $('ev-body').innerHTML = parts.map(p => `<details data-part="${p}" ${localStorage.getItem(partKey(want, p)) === 'closed' ? '' : 'open'}
      class="border-b border-neutral-200 dark:border-neutral-800">
      <summary class="flex items-center gap-2 px-4 h-9 cursor-pointer select-none text-[11px] uppercase tracking-widest text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100">${p}</summary>
      <div class="part-body pb-2"><p class="px-4 text-neutral-400">carregando…</p></div></details>`).join('');
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
// --- Domain Switcher: fuzzy subsequence match (fzf-style), matched letters in bold, Enter opens /domain/<slug> ----------
let domSel = 0, domHits = [];
function fuzzy(q, s) {  // every letter of q, in order, inside s; a lower score is a tighter match
  q = q.toLowerCase(); const low = s.toLowerCase(); let i = -1, last = -1, gaps = 0; const at = [];
  for (const ch of q) { i = low.indexOf(ch, i + 1); if (i < 0) return null; if (last >= 0) gaps += i - last - 1; at.push(i); last = i; }
  return {score: gaps + (at[0] || 0), at};
}
function domRender() {
  const q = $('dom-q').value.trim();
  domHits = D.domains.map(d => ({d, m: fuzzy(q, d.name)})).filter(x => x.m).sort((a, b) => a.m.score - b.m.score);
  domSel = Math.min(domSel, Math.max(domHits.length - 1, 0));
  $('dom-list').innerHTML = domHits.length ? domHits.map(({d, m}, i) => {
    const name = [...d.name].map((ch, k) => m.at.includes(k) ? `<b class="text-neutral-900 dark:text-neutral-100">${esc(ch)}</b>` : esc(ch)).join('');
    return `<div class="dom-row flex items-center justify-between gap-4 px-4 h-9 cursor-pointer ${i === domSel ? 'bg-neutral-100 dark:bg-neutral-900' : ''}" data-i="${i}">
      <span class="text-neutral-600 dark:text-neutral-400">${name}${d.slug === D.base.split('/').pop() ? '<span class="ml-2 text-neutral-400">· atual</span>' : ''}</span>
      <span class="text-neutral-400">${esc(d.entity)}</span></div>`;
  }).join('') : '<p class="px-4 h-9 leading-9 text-neutral-400">nenhum domínio</p>';
  $('dom-list').querySelectorAll('.dom-row').forEach(r => { r.onclick = () => { domSel = +r.dataset.i; domGo(); }; r.onmousemove = () => { if (domSel !== +r.dataset.i) { domSel = +r.dataset.i; domRender(); } }; });
}
const domGo = () => { const h = domHits[domSel]; if (h) location.href = `/domain/${h.d.slug}`; };
const domIsOpen = () => !$('dom').classList.contains('hidden');
function domOpen() { $('dom').classList.remove('hidden'); $('dom').classList.add('flex'); $('dom-q').value = ''; domSel = 0; domRender(); $('dom-q').focus(); }
function domClose() { if (Q.get('embed') === 'switcher') return; $('dom').classList.add('hidden'); $('dom').classList.remove('flex'); }
$('dom-open').onclick = domOpen;
$('dom').onclick = e => { if (e.target === $('dom')) domClose(); };
$('dom-q').oninput = () => { domSel = 0; domRender(); };
$('dom-q').onkeydown = e => {
  if (e.key === 'ArrowDown' || (e.ctrlKey && e.key === 'n')) { domSel = Math.min(domSel + 1, domHits.length - 1); domRender(); e.preventDefault(); }
  else if (e.key === 'ArrowUp' || (e.ctrlKey && e.key === 'p')) { domSel = Math.max(domSel - 1, 0); domRender(); e.preventDefault(); }
  else if (e.key === 'Enter') { domGo(); e.preventDefault(); }
  else if (e.key === 'Escape') { domClose(); e.preventDefault(); e.stopPropagation(); }
};
document.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { domIsOpen() ? domClose() : domOpen(); e.preventDefault(); } });
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
function closeSide() { side.id = null; setQ('ev', ''); setQ('side', ''); setQ('w', ''); setQ('e', ''); const el = $('ev-side'); if (el) el.classList.add('hidden'); }

const TABS = {
  // Domain (DDD, Evans 2003) is the first tab and reuses the Model graph and sidebar: one graph, one style.
  'Domain': () => TABS['Model'](),
  'Model': () => `<div class="h-full flex">
      <div id="graph-col" class="flex-1 min-w-0 flex flex-col">
        <div class="flex items-center justify-between gap-4 px-4 pt-3">${label('Máquina de estados · a partir do Human')}
          <span id="legend" class="flex flex-wrap gap-3 text-neutral-400"></span></div>
        <div class="relative flex-1 min-h-0"><div id="cy" class="absolute inset-0"></div></div>
      </div>
      <aside id="ev-side" class="hidden w-[420px] shrink-0 flex flex-col border-l border-neutral-200 dark:border-neutral-800">
        <div class="shrink-0 flex items-start justify-between gap-3 px-4 pt-3 pb-2">
          <div class="min-w-0"><p id="ev-name" class="font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100"></p>
            <p id="ev-sub" class="text-neutral-400"></p></div>
          <button id="ev-close" title="Esc" class="shrink-0 px-1.5 text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100">✕</button></div>
        <div id="ev-tabs" class="shrink-0 flex px-2 border-b border-neutral-200 dark:border-neutral-800"></div>
        <div id="ev-body" class="relative flex-1 min-h-0 overflow-y-auto"></div>
      </aside></div>`,
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
const KEYS = {'Domain': 'd', 'Model': 'm', 'Visão': 'v', 'Proposed Actions': 'p', 'Observations': 'o', 'Relationships': 'r',
              'Management': 't', 'Eventos': 'e', 'Tipos': 'y'};
// Nerd Font icon per tab (Font Awesome codepoints: sitemap, cubes, eye, lightbulb, search, link, cog, list, tags)
const ICON = {'Domain': '\uf0e8', 'Model': '\uf1b3', 'Visão': '\uf06e', 'Proposed Actions': '\uf0eb', 'Observations': '\uf002',
              'Relationships': '\uf0c1', 'Management': '\uf013', 'Eventos': '\uf03a', 'Tipos': '\uf02c'};
const nf = t => ICON[t] ? `<i class="nf">${ICON[t]}</i>` : '';
const keyed = t => { const k = KEYS[t]; if (!k) return t; const i = t.toLowerCase().indexOf(k);
  return i < 0 ? t : `${t.slice(0, i)}<span class="underline underline-offset-4">${t[i]}</span>${t.slice(i + 1)}`; };
let tab = Q.get('tab') || (location.hash ? decodeURIComponent(location.hash.slice(1)) : 'Domain');
if (!(tab in TABS) || !D.tabs.includes(tab)) tab = 'Domain';
function show(name) {
  if (name !== tab) { setQ('ev', ''); setQ('side', ''); setQ('w', ''); side.id = null; }
  tab = name; setQ('tab', name === 'Domain' ? '' : name);
  $('tabs').innerHTML = Object.keys(TABS).filter(t => D.tabs.includes(t)).map((t, i) =>
    `<a role="tab" title="g ${KEYS[t] || ''}" class="tab shrink-0 whitespace-nowrap px-2 h-9 leading-9 cursor-pointer select-none border-b-2 border-transparent text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 ${t === tab ? 'on' : ''}" data-t="${t}">${nf(t)}${keyed(t)}${COUNT[t] ? `<span class="ml-1.5 text-neutral-400">${COUNT[t]()}</span>` : ''}</a>`).join('');
  $('tabs').querySelectorAll('.tab').forEach(b => b.onclick = () => show(b.dataset.t));
  const wide = GRAPH(tab);
  $('rail').style.display = $('side').style.display = wide ? 'none' : '';
  $('main').innerHTML = TABS[tab]();
  $('main').querySelectorAll('.rec').forEach(r => r.onclick = () => select(r.dataset.id));
  if (tab === 'Visão' && D.home.length)
    frag(`${D.base}/w/${D.state.id}/${D.home[0]}/${encodeURIComponent(D.home[1])}`).then(h => inject($('home'), h));
  else if (tab === 'Visão') mermaid.run({querySelector: '#main .mermaid'});
  if (GRAPH(tab)) { drawGraph(); $('ev-close').onclick = closeSide; }
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
  if (e.key === 'Escape') { popOpen() ? closeWidget() : closeSide(); return; }
  if (popOpen()) return;
});
$('inspector').textContent = JSON.stringify(D.state, null, 2);
if (Q.get('embed') && Q.get('embed') !== 'toolbar') $('bar').style.display = 'none';  // ?embed=1: a widget embeds this view, without the tab bar
if (Q.get('embed') === 'toolbar' && Q.get('sim_tab')) D.tabs.push(Q.get('sim_tab'));  // SIMULADO: an example tab, nothing recorded
show(tab);
if (Q.get('embed')) document.documentElement.dataset.embed = Q.get('embed');
if (Q.get('embed') === 'switcher') domOpen();  // the DomainSwitcher widget: the real switcher, open  // CSS hides what an embed leaves out
if (GRAPH(tab) && Q.get('ev')) {
  const ev = Q.get('ev'), w = Q.get('w');
  openSide(ev);
  if (w) openWidget(ev, w);
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


def _ctx(tid: str, event: str, eid: str | None = None, mode: str = "real"):
    """Context for a real event: ?e=<event id>, else the first event of this type in the journal.
    Its entity (not the one on screen) is what the widget renders."""
    of_type = journal.read({"event": event})
    focus = next((e for e in of_type if e["id"] == eid), None) or (of_type[0] if of_type else None)
    tid = focus[entity_key()] if focus else tid
    entities = [{**t, "title": PROJECT.title_of(journal.read({"id": t["id"], "history": True}), t)} for t in journal.read()]
    return W.EventContext(
        event=event, focus=focus, entity_id=tid,
        events=[e for e in journal.read({"id": tid, "history": True}) if e["event"] == event],
        state=journal.read({"id": tid}) or {}, journal_events=of_type, entities=entities,
        history=tuple(journal.read({"id": tid, "history": True})), mode=mode,
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
def one_widget(slug: str, tid: str, event: str, name: str, e: str = "", mode: str = "real"):
    """One widget, rendered for the popup (mode=sim: simulated, nothing is written)."""
    if not use(slug):
        return _empty(f"domínio {slug} não existe")
    return W.render_one(_ctx(tid, event, e or None, "sim" if mode == "sim" else "real"), name)


@rt("/domain/{slug}/w/{tid}/{event}")
def event_widgets(slug: str, tid: str, event: str, e: str = ""):
    """The list of widgets the project registers for an event, each with its open action."""
    if not use(slug):
        return _empty(f"domínio {slug} não existe")
    return W.render_list(_ctx(tid, event, e or None))


@rt("/")
def index():
    """The first domain; the bar switches between them."""
    return RedirectResponse(f"/domain/{next(iter(DOMAINS))}", status_code=303)


@rt("/domain/{slug}")
def domain(slug: str, req):
    if not use(slug):
        return Title("não encontrado"), Div(f"Domínio {slug} não existe. Há: {', '.join(DOMAINS)}.", cls="p-8 font-mono text-sm")
    entities = journal.read()
    if not entities:
        return Title(PROJECT.NAME), Div(f"Nenhum(a) {PROJECT.ENTITY} no diário.", cls="p-8 font-mono text-sm")
    pick = next((t for t in reversed(entities) if t.get("status") == "open"), entities[-1])
    q = f"?{req.url.query}" if req.url.query else ""  # keep the view (?tab=…&ev=…) across the redirect
    return RedirectResponse(f"/domain/{slug}/t/{pick['id']}{q}", status_code=303)


@rt("/domain/{slug}/t/{tid}")
def tension(slug: str, tid: str):
    if not use(slug):
        return RedirectResponse("/", status_code=303)
    base = PROJECT.BASE
    state = journal.read({"id": tid})
    if not state:
        return Title("não encontrado"), Div(f"{PROJECT.ENTITY} não encontrado(a).", cls="p-8 font-mono text-sm")
    history = journal.read({"id": tid, "history": True})
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

    journal_types: dict[str, int] = {}
    for e in journal.read({"history": True}):
        journal_types[e["event"]] = journal_types.get(e["event"], 0) + 1
    tabs = ["Domain", *[t for t in getattr(PROJECT, "TABS", []) if t != "Domain"]]  # Domain is fixed; TABS is the context's
    domains = [{"slug": s, "name": m.NAME, "entity": getattr(m, "ENTITY", "")} for s, m in DOMAINS.items()]
    payload = json.dumps({"base": base, "name": PROJECT.NAME, "tabs": tabs, "domains": domains, "journal_types": journal_types, "events": history, "state": state, "model": real_model(), "entities": PROJECT.ENTITIES, "home": list(getattr(PROJECT, "HOME", ()))}, ensure_ascii=False).replace("</", "<\\/")
    sub = " · ".join(str(ctx[k]) for k in ("project", "version") if k in ctx)
    head = "px-4 pt-3 pb-1 text-[11px] uppercase tracking-widest text-neutral-500"
    line = "border-neutral-200 dark:border-neutral-800"
    return Title(f"dev-console · {title}"), Style(CSS), Div(
        Div(
            Div("dev-console", cls="shrink-0 pl-4 pr-3 font-semibold text-neutral-900 dark:text-neutral-100"),
            Div(id="tabs", cls="flex-1 min-w-0 flex overflow-x-auto [scrollbar-width:none]"),
            Div(id="keyhint", cls="shrink-0 w-8 text-neutral-400"),
            # dev-console works at the level of a Project
            # dev-console works at the level of a Domain: each one in its own context, /domain/<slug>
            # the current domain; a click or ⌘K opens the Domain Switcher (fuzzy search over an overlay)
            Div(Span("domain ", cls="text-neutral-400"),
                Span(PROJECT.NAME, cls="ml-1 font-semibold text-neutral-800 dark:text-neutral-200"),
                Span("⌘K", cls="ml-2 px-1 rounded border border-neutral-300 dark:border-neutral-700 text-neutral-400"),
                id="dom-open", title="trocar de domínio (⌘K)",
                cls="shrink-0 px-4 truncate cursor-pointer hover:text-neutral-900 dark:hover:text-neutral-100"),
            id="bar", cls=f"h-10 shrink-0 flex items-center border-b {line}",
        ),
        Div(
            Div(Div(PROJECT.ENTITY_PLURAL, cls=head), *rail, id="rail", cls=f"w-56 shrink-0 overflow-y-auto border-r {line}"),
            Div(id="main", cls="flex-1 min-w-0 min-h-0 overflow-y-auto"),
            Div(Div("inspector", cls=head),
                Div(id="inspector", cls="px-4 pb-4 whitespace-pre-wrap break-words text-neutral-600 dark:text-neutral-400"),
                id="side", cls=f"w-80 shrink-0 overflow-y-auto border-l {line}"),
            cls="flex-1 min-h-0 flex",
        ),
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
        Div(
            Div(NotStr('<input id="dom-q" autocomplete="off" spellcheck="false" placeholder="domínio…" '
                       'class="w-full h-11 px-4 bg-transparent border-0 border-b border-neutral-200 dark:border-neutral-800 '
                       'font-mono text-sm text-neutral-900 dark:text-neutral-100 outline-none">'),
                Div(id="dom-list", cls="max-h-[50vh] overflow-y-auto py-1"),
                Div("↑↓ escolher · Enter abrir · Esc fechar", cls="px-4 h-8 leading-8 border-t border-neutral-200 dark:border-neutral-800 text-neutral-400"),
                cls="w-[min(560px,92vw)] rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 shadow-2xl"),
            id="dom", cls="hidden fixed inset-0 z-[10001] items-start justify-center pt-[16vh] bg-black/40 backdrop-blur-[1px]",
        ),
        Script(payload, type="application/json", id="data"),
        Script(src="https://cdn.jsdelivr.net/npm/cytoscape@3/dist/cytoscape.min.js"),
        # fCoSE (Balci & Dogrusoz 2022): force-directed with constraints; the Human is pinned in the centre
        Script(src="https://cdn.jsdelivr.net/npm/layout-base@2.0.1/layout-base.js"),
        Script(src="https://cdn.jsdelivr.net/npm/cose-base@2.2.0/cose-base.js"),
        Script(src="https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.js"),
        Script(JS, type="module"),
        cls="h-screen flex flex-col font-mono text-xs bg-white dark:bg-neutral-950",
    )


def _serve(port: int) -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dev-console for an event-sourced project")
    parser.add_argument("--project", action="append", help="path to a dev_console_project.py (repeat: one domain each)")
    parser.add_argument("--port", type=int, default=5057)
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
