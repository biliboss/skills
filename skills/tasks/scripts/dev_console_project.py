"""Tasks in the dev-console: a task is explained, and the receiver teaches it back."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fasthtml.common import Div, Li, Ol, P, Script, Span, Ul  # noqa: E402
from tasks import TasksJournal  # noqa: E402

NAME = "Tasks"
SLUG = "tasks"
SOURCE = Path(__file__).parent / "tasks.py"  # the file with EVENTS
ENTITY = "Task"
ENTITY_PLURAL = "tarefas"
ENTITIES = {"task": "Task", "understanding": "Understanding"}
ENTITY_KEY = "task_id"
PROJECTOR = "_project"

journal = TasksJournal()


def title_of(history: list[dict], state: dict) -> str:
    return state.get("title", "")


K = "text-[11px] uppercase tracking-widest text-neutral-500"
BODY = "font-sans text-[15px] leading-relaxed text-neutral-800 dark:text-neutral-200"
SKILL_MD = Path(__file__).parent.parent / "SKILL.md"
INPUT_PY = Path(__file__).parent / "input.py"


def _skill_meta() -> tuple[str, str, list[str]]:
    """The skill's real name, description (without the trigger list) and the steps of its Explain section."""
    import re

    text = SKILL_MD.read_text()
    front = text.split("---")[1]
    name = next((l.split(":", 1)[1].strip() for l in front.splitlines() if l.startswith("name:")), "tasks")
    desc = " ".join(l.strip() for l in front.split("description:", 1)[1].split("metadata:")[0].splitlines()[1:])
    body = text.split("## Explain", 1)[1].split("\n## ", 1)[0] if "## Explain" in text else ""
    steps = [re.sub(r"`([^`]+)`", r"\1", m) for m in re.findall(r"^\d+\.\s+(.+)$", body, re.M)]
    return name, desc.split(" Use when")[0], steps


def _input_model() -> dict:
    """The Input contract, read from input.py with ast (never imported): {class: {doc, fields: [(name, type)], harness}}."""
    import ast

    out = {}
    for node in ast.parse(INPUT_PY.read_text()).body:
        if isinstance(node, ast.ClassDef):
            flds, harness = [], False
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    if "ClassVar" in ast.unparse(st.annotation):
                        harness = harness or st.target.id == "assembled_by_harness"
                    else:
                        flds.append((st.target.id, ast.unparse(st.annotation)))
            out[node.name] = {"doc": (ast.get_docstring(node) or "").splitlines()[0], "fields": flds, "harness": harness}
    return out


def _input_graph(model: dict) -> list[dict]:
    """Cytoscape elements: every value object of Input; one that holds others is a compound node around them."""
    els, pos = [], {}
    roots = [(f, t) for f, t in model["Input"]["fields"]]
    y = 0
    for _, typ in roots:
        kids = [t for _, t in model[typ]["fields"] if t in model]
        if kids:  # a compound: its children stacked inside it
            els.append({"data": {"id": typ, "label": typ, "harness": model[typ]["harness"], "doc": model[typ]["doc"]},
                        "classes": "group" + (" harness" if model[typ]["harness"] else "")})
            y += 50
            for k in kids:
                leaf = [n for n, _ in model[k]["fields"]]
                els.append({"data": {"id": k, "parent": typ, "label": f"{k}\n{', '.join(leaf)}", "doc": model[k]["doc"]},
                            "position": {"x": 0, "y": y}, "classes": "leaf harness" if model[typ]["harness"] else "leaf"})
                y += 74
            y += 30
        else:
            leaf = [n for n, _ in model[typ]["fields"]]
            els.append({"data": {"id": typ, "label": f"{typ}\n{', '.join(leaf)}", "doc": model[typ]["doc"]},
                        "position": {"x": 0, "y": y}, "classes": "leaf"})
            y += 90
    mid = (y - 90) / 2
    els.append({"data": {"id": "Input", "label": "Input"}, "position": {"x": 300, "y": mid}, "classes": "hub"})
    els.append({"data": {"id": "task.explained", "label": "Task\nExplained"}, "position": {"x": 540, "y": mid}, "classes": "event"})
    for _, typ in roots:
        els.append({"data": {"id": f"{typ}>Input", "source": typ, "target": "Input"}})
    els.append({"data": {"id": "Input>task.explained", "source": "Input", "target": "task.explained", "label": "explain"}})
    return els


def skill(ctx):
    """Task Skill: how the tasks skill handles this event, generated from the real SKILL.md and scripts/input.py."""
    import json

    name, desc, steps = _skill_meta()
    model = _input_model()
    els = json.dumps(_input_graph(model), ensure_ascii=False)
    docs = [(c, m["doc"], m["harness"]) for c, m in model.items() if c != "Input"]
    script = """
(() => {
  const box = document.getElementById('skill-input-cy'); if (!box || !window.cytoscape) return;
  const dark = matchMedia('(prefers-color-scheme: dark)').matches, fg = dark ? '#e5e5e5' : '#262626',
        dim = dark ? '#737373' : '#a3a3a3', line = dark ? '#404040' : '#d4d4d4', ink = '#8b8ef0';
  const cy = cytoscape({container: box, elements: ELS, layout: {name: 'preset', fit: true, padding: 24},
    userZoomingEnabled: false, userPanningEnabled: false, boxSelectionEnabled: false, autoungrabify: true,
    style: [
      {selector: 'node', style: {label: 'data(label)', 'text-wrap': 'wrap', 'text-valign': 'center', 'text-halign': 'center',
        'font-family': 'ui-monospace, monospace', 'font-size': 12, color: fg, shape: 'round-rectangle', width: 190, height: 50,
        'background-color': dark ? '#171717' : '#fafafa', 'border-width': 1.5, 'border-color': line}},
      {selector: 'node.harness', style: {'border-style': 'dashed', color: dim}},
      {selector: 'node.group', style: {'text-valign': 'top', 'text-halign': 'center', 'text-margin-y': -6, 'font-size': 12,
        'background-opacity': 0, 'border-style': 'dashed', 'border-color': dim, padding: 14, color: dim}},
      {selector: 'node.hub', style: {width: 110, height: 44, 'font-weight': 'bold', 'border-color': fg}},
      {selector: 'node.event', style: {width: 140, height: 56, 'background-color': ink, 'border-color': ink, color: '#0a0a0a',
        'font-weight': 'bold', 'font-size': 14}},
      {selector: 'edge', style: {width: 1.5, 'line-color': line, 'target-arrow-color': line, 'target-arrow-shape': 'triangle',
        'curve-style': 'straight', 'arrow-scale': 0.8, label: 'data(label)', 'font-family': 'ui-monospace, monospace',
        'font-size': 12, color: ink, 'text-background-opacity': 1, 'text-background-color': dark ? '#0a0a0a' : '#fff'}},
      {selector: 'edge[source = "Input"]', style: {'line-color': ink, 'target-arrow-color': ink, width: 2.5}},
    ]});
  new ResizeObserver(() => { if (box.clientWidth && box.clientHeight) { cy.resize(); cy.fit(undefined, 24); } }).observe(box);
})();
""".replace("ELS", els)
    return Div(
        Div(Span("Task Skill", cls="font-sans text-lg font-semibold"),
            Span(f"skill {name}", cls="ml-3 font-mono text-sm text-neutral-400"), cls="flex items-baseline"),
        P(desc, cls=f"{BODY} mt-1 text-neutral-500 dark:text-neutral-400"),
        Div("Input", Span(" · de scripts/input.py", cls="normal-case tracking-normal text-neutral-400"), cls=f"{K} mt-6"),
        Div(id="skill-input-cy", cls="mt-2 h-[460px] w-full rounded border border-neutral-200 dark:border-neutral-800"),
        Ul(*[Li(Span(c, cls="font-mono text-sm"), Span(f" {d}", cls=f"{BODY} text-neutral-600 dark:text-neutral-400"),
                Span(" · harness", cls="font-mono text-xs text-neutral-400") if h else "", cls="mt-1") for c, d, h in docs],
           cls="mt-3"),
        Div("O que a skill faz", cls=f"{K} mt-6"),
        Ol(*[Li(step, cls=f"{BODY} mt-1") for step in steps], cls="mt-2 ml-5 list-decimal"),
        Script(script),
        cls="p-5 w-[min(860px,86vw)]", data_real_only="1",
    )


skill.fake = True  # generated from the skill's files, not from journal events: it renders with an empty journal too

WIDGETS: dict = {
    "task.explained": [skill],
}
