# /// script
# requires-python = ">=3.10"
# dependencies = ["python-fasthtml>=0.14", "monsterui>=1.0.48"]
# ///
"""dev-console: a read-only, full-screen console for an event-sourced project in development (FastHTML + MonsterUI).

Run:  uv run --script dev-console.py --project <path/to/dev_console_project.py> [--port 5057]
A project file says what to show (see the skill's references/project-contract.md):
  NAME, SOURCE (file with the EVENTS registry {category: {command: event}}), ENTITY, ENTITY_PLURAL,
  ENTITIES ({category: entity name}), PROJECTOR (the fold function), journal (.read(query)), title_of(), WIDGETS.
Layout: tabs first; the entity rail on the left; the selected record on the right. Model = the state machine.
Keys (vim-style goto): g m Model, g v Visão, g p Proposed Actions, g o Observations, g r Relationships,
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


if "--project" in sys.argv:  # the module body needs the project, so read the flag before argparse runs
    os.environ["DEV_CONSOLE_PROJECT"] = str(Path(sys.argv[sys.argv.index("--project") + 1]).expanduser().resolve())
if not os.environ.get("DEV_CONSOLE_PROJECT"):
    sys.exit("dev-console: pass --project <path/to/dev_console_project.py> (or set DEV_CONSOLE_PROJECT)")
PROJECT = load_project(os.environ["DEV_CONSOLE_PROJECT"])
from fasthtml.common import Div, Li, NotStr, P, Script, Span, Style, Title, Ul, fast_app  # noqa: E402
from monsterui.all import Theme  # noqa: E402
from starlette.responses import RedirectResponse  # noqa: E402

app, rt = fast_app(hdrs=Theme.neutral.headers(mode="auto"), live=True)  # live: the browser reloads on save
journal = PROJECT.journal

# The real code, read from disk on every request and pushed again when the file changes.
SOURCE = Path(PROJECT.SOURCE)


def derive(events: dict) -> dict:
    """Everything the screen shows comes from EVENTS ({category: {command: event}}, ordered):
    the categories and their events, the commands, and the graph edges (created opens every other
    category; inside a category each event follows the previous one)."""
    lifecycle = {c: list(cmds.values()) for c, cmds in events.items()}
    commands = {f"{c}.{ev}": cmd for c, cmds in events.items() for cmd, ev in cmds.items()}
    root = next(f"{c}.{evs[0]}" for c, evs in lifecycle.items())
    nxt: dict[str, list[str]] = {}
    for c, evs in lifecycle.items():
        chain = [f"{c}.{ev}" for ev in evs]
        if chain[0] != root:
            nxt.setdefault(root, []).append(chain[0])
        for x, y in zip(chain, chain[1:]):
            nxt.setdefault(x, []).append(y)
    return {"lifecycle": lifecycle, "commands": commands, "next": nxt, "root": root}


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
                        # ast drops comments: take the comment line right above the key, if any
                        above = src[k.lineno - 2].strip() if k.lineno >= 2 else ""
                        note = f"  {above}" if above.startswith("#") else ""
                        lines.append({"line": k.lineno, "code": f"    {ast.literal_eval(k)} = {ast.unparse(v)}{note}"})
                    # Commands by category, straight from EVENTS: each command records one event.
                    model = derive(live_events())
                    for cat, cmds in live_events().items():
                        lines.append({"line": None, "code": ""})
                        lines.append({"line": None, "code": f"    # {cat}"})
                        for cmd, ev in cmds.items():
                            if f"{cat}.{ev}" == model["root"]:
                                lines.append({"line": None, "code": "    @staticmethod"})
                            lines.append({"line": None, "code": f"    def {cmd}(value): ...  # -> {cat}.{ev}"})
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
    return {"file": SOURCE.name, "mtime": SOURCE.stat().st_mtime, "lines": lines,
            "coverage": W.coverage(live_events()), **derive(live_events())}


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
    return [(widget_name(fn), doc(fn)) for fn in _widgets(event)] + [("Observability", doc(observability))]


def render_list(ctx: EventContext):
    f = ctx.focus
    head = (P(f"dados reais: {f['id'][:8]} · {_when(f['at'])} · {PROJECT.ENTITY.lower()} {f[ENTITY_KEY][:8]}",
              cls="px-4 pt-3 text-neutral-400") if f else P(f"nenhum {ctx.event} no diário ainda", cls="px-4 pt-3 text-neutral-400"))
    return Div(head, Ul(*[
        Li(Div(P(name, cls="font-semibold text-neutral-800 dark:text-neutral-200"),
               P(desc or "todo evento", cls="text-neutral-400"), cls="min-w-0"),
           NotStr(f'<button class="w-open shrink-0 px-2 h-7 rounded border border-neutral-300 dark:border-neutral-700 '
                  f'text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900" data-w="{name}">abrir</button>'),
           cls="flex items-center justify-between gap-3 px-4 py-3 border-b border-neutral-200 dark:border-neutral-800")
        for name, desc in available(ctx.event)
    ]))


def render_one(ctx: EventContext, name: str):
    if ctx.focus is None and name != "Observability":
        return _empty(f"Nenhum evento {ctx.event} no diário ainda: o widget só renderiza dados reais.")
    if name == "Observability":
        return observability(ctx)
    fn = next((f for f in _widgets(ctx.event) if widget_name(f) == name), None)
    return fn(ctx) if fn else _empty(f"Widget {name} não está registrado para {ctx.event}.")


def coverage(events_by_category: dict) -> dict[str, list[str]]:
    return {f"{c}.{ev}": [widget_name(f) for f in _widgets(f"{c}.{ev}")]
            for c, cmds in events_by_category.items() for ev in cmds.values()}


W = SimpleNamespace(EventContext=EventContext, render_list=render_list, render_one=render_one, coverage=coverage)
ENTITY_KEY = getattr(PROJECT, "ENTITY_KEY", "tension_id")  # the journal field that names the entity


CSS = """
html,body{height:100%;overflow:hidden}
.tab.on{color:rgb(23 23 23);border-color:rgb(23 23 23)} .dark .tab.on{color:rgb(245 245 245);border-color:rgb(245 245 245)}
.rec.sel{background:rgb(229 229 229)} .dark .rec.sel{background:rgb(38 38 38)}
.mermaid svg{max-width:100%}
"""

JS = r"""
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const D = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
mermaid.initialize({startOnLoad:false, theme:'base', fontFamily:'inherit', themeVariables:{
  primaryColor: dark?'#262626':'#fafafa', primaryBorderColor: dark?'#525252':'#a3a3a3',
  primaryTextColor: dark?'#e5e5e5':'#262626', lineColor: dark?'#737373':'#a3a3a3'}});

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
new EventSource('/source/stream').onmessage = ev => {
  D.model = JSON.parse(ev.data);
  if (tab === 'Model' && $('cy')) { drawGraph(); if (side.id) openSide(side.id); }
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
  const colorOf = id => PATH[id.split('.')[0]];
  // Entity.Event: management happens to the Tension itself; the others to the Value Object of their category.
  const ENT = D.entities || {};
  const pascal = w => w.split('_').map(x => x[0].toUpperCase() + x.slice(1)).join('');
  // Rays: each category leaves the centre at its own angle; depth = steps from created along the ray.
  const ANGLE = {management: -90, observation: -18, reasoning: 36, relationship: 144, action: 198};
  const R = 185;
  const pos = id => {
    if (id === 'human') return {x: 0, y: R * 1.1};
    if (id === M().root) return {x: 0, y: 0};
    const c = id.split('.')[0], d = depth[id] ?? 1, k = `${c}:${d}`;
    const sibs = Object.keys(depth).filter(n => n.split('.')[0] === c && depth[n] === d && n !== M().root);
    const cats = Object.keys(M().lifecycle).filter(x => x !== M().root.split('.')[0]);
    const a = (ANGLE[c] ?? (-18 + 72 * cats.indexOf(c))) * Math.PI / 180;
    // wide nodes on a horizontal ray eat the edge: add room in proportion to |cos a|
    const r = d * (R + 80 * Math.abs(Math.cos(a)));
    const gap = 66 + 110 * Math.abs(Math.sin(a));  // siblings side by side need room for the label width
    const i = sibs.indexOf(id), off = (i - (sibs.length - 1) / 2) * gap;
    return {x: Math.cos(a) * r - Math.sin(a) * off, y: Math.sin(a) * r + Math.cos(a) * off};
  };
  const name = id => { const [c, v] = id.split('.'); return `${ENT[c] || pascal(c)}.${pascal(v)}`; };
  const depth = {[M().root]: 0}, queue = [M().root];  // rings: steps from created
  while (queue.length) { const a = queue.shift(); (M().next[a] || []).forEach(b => { if (!(b in depth)) { depth[b] = depth[a] + 1; queue.push(b); } }); }
  Object.entries(M().lifecycle).forEach(([cat, verbs]) => verbs.forEach(v => {
    const id = `${cat}.${v}`;
    nodes.push({position: pos(id), data: {id, color: PATH[cat], label: name(id).replace('.', '\n')}, classes: [D.journal_types[id] ? 'used' : '', id === M().root ? 'root' : ''].join(' ')});
  }));
  // ISO 9241-210 (human-centred design): a generic Human is who acts; the first command creates the Tension.
  nodes.push({position: pos('human'), data: {id: 'human', label: 'Human', color: ink}, classes: 'human'});
  edges.push({data: {id: `human>${M().root}`, source: 'human', target: M().root, color: colorOf(M().root),
    label: M().commands[M().root]}, classes: 'walked'});
  Object.entries(M().next).forEach(([a, bs]) => bs.forEach(b =>
    edges.push({data: {id: `${a}>${b}`, source: a, target: b, color: colorOf(b), label: M().commands[b]}, classes: D.journal_types[a] && D.journal_types[b] ? 'walked' : ''})));
  const cy = cytoscape({
    container: $('cy'), elements: {nodes, edges}, wheelSensitivity: 0.2,
    layout: {name: 'preset', padding: 16}, maxZoom: 3,
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
  cy.on('tap', 'node', ev => openSide(ev.target.id()));
  window.__cy = cy;
}

// --- the event sidebar: contextual, with its own tabs -----------------------------------------------------
// UI state lives in the URL query: tab, ev (event in the sidebar), side (sidebar tab), w (widget popup).
const Q = new URLSearchParams(location.search);
function setQ(k, v) { v ? Q.set(k, v) : Q.delete(k); const q = Q.toString();
  history.replaceState(null, '', location.pathname + (q ? '?' + q : '')); }
let side = {id: null, tab: Q.get('side') || 'Widgets'};
const SIDE_TABS = {
  'Widgets': id => fetch(`/w/${D.state.id}/${id}?e=${Q.get('e') || ''}`).then(r => r.text()),
  'Código': id => {
    const cmd = M().commands[id];
    const html = M().lines.map(l => {
      const hit = cmd && l.code.trim().startsWith(`def ${cmd}(`);
      return `<div class="flex ${hit ? 'bg-neutral-200 dark:bg-neutral-800' : ''}" ${hit ? 'id="hit"' : ''}><span class="w-10 shrink-0 pr-3 text-right select-none text-neutral-300 dark:text-neutral-700">${l.line ?? ''}</span>`
        + `<span class="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]">${codeBlock(l.code) || '&nbsp;'}</span></div>`;
    }).join('');
    return Promise.resolve(`<p class="px-4 pt-3 text-neutral-400">${esc(M().file)} · ao vivo</p><div class="px-2 py-3 leading-6 text-neutral-700 dark:text-neutral-300">${html}</div>`);
  },
  'JSON': id => Promise.resolve(`<pre class="m-0 p-4 !bg-transparent whitespace-pre-wrap text-neutral-600 dark:text-neutral-400">${esc(JSON.stringify(E.filter(e => e.event === id), null, 2))}</pre>`),
};
function openSide(id) {
  side.id = id; setQ('ev', id);
  $('ev-side').classList.remove('hidden');
  if (id === 'human') {
    $('ev-name').textContent = 'Human';
    $('ev-sub').textContent = 'estado inicial · ISO 9241-210';
    $('ev-tabs').innerHTML = '';
    $('ev-body').innerHTML = `<p class="p-4 font-sans text-sm text-neutral-700 dark:text-neutral-300">Quem age. Começa pelo comando <b>${M().commands[M().root]}</b>, que grava ${M().root}.</p>`;
    return;
  }
  const [c, v] = id.split('.'), n = E.filter(e => e.event === id).length, w = (M().coverage || {})[id] || [];
  $('ev-name').textContent = `${c}.${v}`;
  $('ev-sub').textContent = `comando ${M().commands[id]} · ${n} nesta tensão · ${w.length ? w.join(', ') : 'só Observability'}`;
  renderSide();
}
function renderSide() {
  $('ev-tabs').innerHTML = Object.keys(SIDE_TABS).map(t =>
    `<a class="tab shrink-0 px-2 h-8 leading-8 cursor-pointer border-b-2 border-transparent text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 ${t === side.tab ? 'on' : ''}" data-s="${t}">${t}</a>`).join('');
  $('ev-tabs').querySelectorAll('a').forEach(a => a.onclick = () => { side.tab = a.dataset.s; setQ('side', side.tab === 'Widgets' ? '' : side.tab); renderSide(); });
  const want = side.id;
  SIDE_TABS[side.tab](want).then(html => {
    if (side.id !== want) return;
    $('ev-body').innerHTML = html;
    $('ev-body').querySelectorAll('.w-open').forEach(b => b.onclick = () => openWidget(want, b.dataset.w));
    // scroll only the sidebar (scrollIntoView also scrolled #main and pushed the graph out of view)
    const hit = document.getElementById('hit'), body = $('ev-body');
    if (hit) body.scrollTop = hit.offsetTop - body.clientHeight / 2;
  });
}
function openWidget(id, name) {
  setQ('w', name);
  $('pop-name').textContent = name;
  $('pop-sub').textContent = Q.get('e') ? `${id} · evento ${Q.get('e').slice(0, 8)}` : `${id} · primeiro evento real do diário`;
  $('pop-body').innerHTML = '<p class="text-neutral-400">carregando…</p>';
  $('pop').classList.remove('hidden'); $('pop').classList.add('flex');
  fetch(`/w/${D.state.id}/${id}/${encodeURIComponent(name)}?e=${Q.get('e') || ''}`).then(r => r.text()).then(h => { $('pop-body').innerHTML = h; });
}
function closeWidget() { setQ('w', ''); $('pop').classList.add('hidden'); $('pop').classList.remove('flex'); }
const popOpen = () => !$('pop').classList.contains('hidden');
$('pop-close').onclick = closeWidget;
$('pop').onclick = e => { if (e.target === $('pop')) closeWidget(); };
function closeSide() { side.id = null; setQ('ev', ''); setQ('side', ''); setQ('w', ''); setQ('e', ''); const el = $('ev-side'); if (el) el.classList.add('hidden'); }

const TABS = {
  'Model': () => `<div class="h-full flex">
      <div class="flex-1 min-w-0 flex flex-col">
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

const KEYS = {'Model': 'm', 'Visão': 'v', 'Proposed Actions': 'p', 'Observations': 'o', 'Relationships': 'r',
              'Management': 't', 'Eventos': 'e', 'Tipos': 'y'};
const keyed = t => { const k = KEYS[t]; if (!k) return t; const i = t.toLowerCase().indexOf(k);
  return i < 0 ? t : `${t.slice(0, i)}<span class="underline underline-offset-4">${t[i]}</span>${t.slice(i + 1)}`; };
let tab = Q.get('tab') || (location.hash ? decodeURIComponent(location.hash.slice(1)) : 'Model');
if (!(tab in TABS)) tab = 'Model';
function show(name) {
  if (name !== tab) { setQ('ev', ''); setQ('side', ''); setQ('w', ''); side.id = null; }
  tab = name; setQ('tab', name === 'Model' ? '' : name);
  $('tabs').innerHTML = Object.keys(TABS).map((t, i) =>
    `<a role="tab" title="g ${KEYS[t] || ''}" class="tab shrink-0 whitespace-nowrap px-2 h-9 leading-9 cursor-pointer select-none border-b-2 border-transparent text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 ${t === tab ? 'on' : ''}" data-t="${t}">${keyed(t)}${COUNT[t] ? `<span class="ml-1.5 text-neutral-400">${COUNT[t]()}</span>` : ''}</a>`).join('');
  $('tabs').querySelectorAll('.tab').forEach(b => b.onclick = () => show(b.dataset.t));
  const wide = tab === 'Model';
  $('rail').style.display = $('side').style.display = wide ? 'none' : '';
  $('main').innerHTML = TABS[tab]();
  $('main').querySelectorAll('.rec').forEach(r => r.onclick = () => select(r.dataset.id));
  if (tab === 'Visão') mermaid.run({querySelector: '#main .mermaid'});
  if (tab === 'Model') { drawGraph(); $('ev-close').onclick = closeSide; }
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
    if (t && t in TABS) { show(t); e.preventDefault(); }
    return;
  }
  if (e.key === 'g') { $('keyhint').textContent = 'g…'; pending = setTimeout(() => { pending = null; $('keyhint').textContent = ''; }, 1200); return; }
  if (e.key === 'Escape') { popOpen() ? closeWidget() : closeSide(); return; }
  if (popOpen()) return;
});
$('inspector').textContent = JSON.stringify(D.state, null, 2);
show(tab);
if (tab === 'Model' && Q.get('ev')) {
  const ev = Q.get('ev'), w = Q.get('w');
  openSide(ev);
  if (w) openWidget(ev, w);
}
"""


title_of = PROJECT.title_of


@rt("/source/stream")
async def source_stream():
    """Server-sent events: the real model again whenever the project SOURCE changes on disk."""
    import asyncio

    from starlette.responses import StreamingResponse

    async def gen():
        last = None
        while True:
            m = SOURCE.stat().st_mtime
            if m != last:
                last = m
                yield f"data: {json.dumps(real_model(), ensure_ascii=False)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")


def _ctx(tid: str, event: str, eid: str | None = None):
    """Context for a real event: ?e=<event id>, else the first event of this type in the journal.
    Its entity (not the one on screen) is what the widget renders."""
    of_type = journal.read({"event": event})
    focus = next((e for e in of_type if e["id"] == eid), None) or (of_type[0] if of_type else None)
    tid = focus[ENTITY_KEY] if focus else tid
    entities = [{**t, "title": PROJECT.title_of(journal.read({"id": t["id"], "history": True}), t)} for t in journal.read()]
    return W.EventContext(
        event=event, focus=focus, entity_id=tid,
        events=[e for e in journal.read({"id": tid, "history": True}) if e["event"] == event],
        state=journal.read({"id": tid}) or {}, journal_events=of_type, entities=entities,
    )


@rt("/w/{tid}/{event}/{name}")
def one_widget(tid: str, event: str, name: str, e: str = ""):
    """One widget, rendered for the popup."""
    return W.render_one(_ctx(tid, event, e or None), name)


@rt("/w/{tid}/{event}")
def event_widgets(tid: str, event: str, e: str = ""):
    """The list of widgets the project registers for an event, each with its open action."""
    return W.render_list(_ctx(tid, event, e or None))


@rt("/")
def index():
    tensions = journal.read()
    if not tensions:
        return Title(PROJECT.NAME), Div(f"Nenhum(a) {PROJECT.ENTITY} no diário.", cls="p-8 font-mono text-sm")
    pick = next((t for t in reversed(tensions) if t["status"] == "open"), tensions[-1])
    return RedirectResponse(f"/t/{pick['id']}", status_code=303)


@rt("/t/{tid}")
def tension(tid: str):
    state = journal.read({"id": tid})
    if not state:
        return Title("não encontrado"), Div(f"{PROJECT.ENTITY} não encontrado(a).", cls="p-8 font-mono text-sm")
    history = journal.read({"id": tid, "history": True})
    title = title_of(history, state)
    ctx = state.get("context") or {}

    rail = []
    for t in sorted(journal.read(), key=lambda s: (s["status"] != "open", s["updated_at"])):
        on = t["id"] == tid
        rail.append(Div(
            Div(title_of(journal.read({"id": t["id"], "history": True}), t),
                cls="truncate " + ("font-semibold text-neutral-900 dark:text-neutral-100" if on else "text-neutral-600 dark:text-neutral-400")),
            Div(f"{t['status']} · {t['event_count']} eventos", cls="text-neutral-400"),
            onclick=f"location.href='/t/{t['id']}'",
            cls="px-4 py-2 cursor-pointer border-l-2 " + (
                "border-neutral-900 dark:border-neutral-100 bg-neutral-100 dark:bg-neutral-900" if on
                else "border-transparent hover:bg-neutral-100 dark:hover:bg-neutral-900"),
        ))

    journal_types: dict[str, int] = {}
    for e in journal.read({"history": True}):
        journal_types[e["event"]] = journal_types.get(e["event"], 0) + 1
    payload = json.dumps({"journal_types": journal_types, "events": history, "state": state, "model": real_model(), "entities": PROJECT.ENTITIES}, ensure_ascii=False).replace("</", "<\\/")
    sub = " · ".join(str(ctx[k]) for k in ("project", "version") if k in ctx)
    head = "px-4 pt-3 pb-1 text-[11px] uppercase tracking-widest text-neutral-500"
    line = "border-neutral-200 dark:border-neutral-800"
    return Title(f"dev-console · {title}"), Style(CSS), Div(
        Div(
            Div("dev-console", cls="shrink-0 pl-4 pr-3 font-semibold text-neutral-900 dark:text-neutral-100"),
            Div(id="tabs", cls="flex-1 min-w-0 flex overflow-x-auto [scrollbar-width:none]"),
            Div(id="keyhint", cls="shrink-0 w-8 text-neutral-400"),
            # dev-console works at the level of a Project
            Div(Span("project ", cls="text-neutral-400"), Span(PROJECT.NAME, cls="font-semibold text-neutral-800 dark:text-neutral-200"),
                Span(f" · {journal.path.name}", cls="text-neutral-400"), title=str(journal.path),
                cls="shrink-0 px-4 truncate"),
            cls=f"h-10 shrink-0 flex items-center border-b {line}",
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
                    Div("✕", id="pop-close", title="Esc", cls="shrink-0 px-2 cursor-pointer text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100"),
                    cls="shrink-0 flex items-start justify-between gap-4 px-6 pt-5 pb-3 border-b border-neutral-200 dark:border-neutral-800"),
                Div(id="pop-body", cls="flex-1 min-h-0 overflow-y-auto px-6 py-5"),
                cls="w-[min(860px,92vw)] max-h-[82vh] flex flex-col rounded-lg border border-neutral-300 dark:border-neutral-700 "
                    "bg-white dark:bg-neutral-950 shadow-2xl",
            ),
            id="pop", cls="hidden fixed inset-0 z-[10000] items-center justify-center bg-black/40 backdrop-blur-[1px]",
        ),
        Script(payload, type="application/json", id="data"),
        Script(src="https://cdn.jsdelivr.net/npm/cytoscape@3/dist/cytoscape.min.js"),
        Script(JS, type="module"),
        cls="h-screen flex flex-col font-mono text-xs bg-white dark:bg-neutral-950",
    )


def _serve(port: int) -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dev-console for an event-sourced project")
    parser.add_argument("--project", default=os.environ.get("DEV_CONSOLE_PROJECT"), help="path to dev_console_project.py")
    parser.add_argument("--port", type=int, default=5057)
    args = parser.parse_args()
    if not args.project:
        parser.error("--project is required (or DEV_CONSOLE_PROJECT)")
    os.environ["DEV_CONSOLE_PROJECT"] = str(Path(args.project).resolve())
    from watchfiles import run_process

    # Hot reload: restart on any change in this file or the project folder; live=True reloads the page.
    run_process(Path(__file__).parent, Path(args.project).resolve().parent, target=_serve, args=(args.port,))
