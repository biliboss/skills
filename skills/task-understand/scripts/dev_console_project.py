"""Tasks in the dev-console: a task is explained, and the receiver teaches it back."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fasthtml.common import A, Div, Figcaption, Figure, H2, Img, Li, NotStr, Ol, P, Pre, Script, Span, Ul  # noqa: E402
from tasks import (MEDIA_DIR, TRANSITIONS, BeforeAfter, Commit, Delivery, Effort, ExecutionResult, Harness,  # noqa: E402,F401
                   Journey, Method, Model, Picture, PullRequest, PullRequestState, SessionRef, TasksJournal, result_from)

NAME = "Biliboss Skills - Tasks"
SLUG = "tasks"
SOURCE = Path(__file__).parent / "tasks.py"  # the file with EVENTS
ENTITY = "Task"
ENTITY_PLURAL = "tarefas"
ENTITIES = {"task": "Task", "understanding": "Understanding", "feedback": "Feedback", "option": "Option", "style": "Style"}
ENTITY_KEY = "task_id"
PROJECTOR = "_project"

journal = TasksJournal()
MEDIA = MEDIA_DIR  # the console serves /domain/tasks/media?f=<path> from here

# The Human explains the task and, after the teach-back, confirms the understanding: both edges leave the Human.
INITIAL = ["task.explained", "understanding.confirmed"]


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
    name = next((l.split(":", 1)[1].strip() for l in front.splitlines() if l.startswith("name:")), "task-understand")
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

# --- Task Executed: the Task List, the Task Detail and the Tasks view (the future Tasks tab), composed -------------

BASE = "/domain/tasks"  # set again by the console (its own BASE for this domain)


def _title(text: str):
    """Every widget starts with its title."""
    return H2(text, cls="mb-3 font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100")


def _when(iso: str) -> str:
    from datetime import datetime

    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")


def task_list(ctx):
    """Task List: the executed tasks, the newest first; a row opens its Task Detail."""
    rows = []
    # in the Task Results tab of a domain: only that domain's tasks (the tasks domain itself shows them all)
    done = [t for t in ctx.entities if t.get("status") == "executed"
            and (not ctx.domain or t.get("domain") == ctx.domain)]
    for t in sorted(done, key=lambda t: t.get("updated_at", ""), reverse=True):
        on = t["id"] == ctx.entity_id
        rows.append(A(
            Div(P(t.get("title", ""), cls="font-sans text-[15px] leading-snug " + (
                "font-semibold text-neutral-900 dark:text-neutral-100" if on else "text-neutral-700 dark:text-neutral-300")),
                P(_when(t["updated_at"]), cls="mt-0.5 text-xs text-neutral-400"),
                cls="min-w-0"),
            href=(f"/domain/{ctx.domain}?tab=Task+Results&task={t['id']}" if ctx.domain
                  else f"{BASE}/t/{t['id']}?ev=task.executed&w=Tasks"), target="_top",
            cls="block px-3 py-2.5 rounded no-underline hover:bg-neutral-100 dark:hover:bg-neutral-900 "
                + ("bg-neutral-100 dark:bg-neutral-900" if on else "")))
    return Div(_title("Tarefas executadas"),
               Div(*rows, cls="flex flex-col gap-0.5") if rows else P("nenhuma tarefa executada ainda", cls="text-neutral-400"))


def _executed(ctx) -> dict | None:
    """The task's last task.executed event (its result), or None."""
    runs = [e for e in (ctx.history or []) if e["event"] == "task.executed"]
    return runs[-1] if runs else None


def _mock(title: str, lines: list[str], tone: str = "#8b8ef0") -> str:
    """A small SVG picture as a data URI: example images for the prototype (no real screenshots yet)."""
    import base64

    rows = "".join(f'<text x="24" y="{92 + i * 30}" font-size="17" fill="#a3a3a3">{t}</text>' for i, t in enumerate(lines))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" rx="14" '
           f'fill="#171717"/><rect x="0" y="0" width="640" height="52" rx="14" fill="{tone}" opacity="0.18"/>'
           f'<text x="24" y="34" font-size="20" font-weight="600" fill="#e5e5e5">{title}</text>{rows}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# Design first, on the code's own value object: a run like the one that implemented this skill (task b77a228e).
# The screen is drawn from ExecutionResult, so the design cannot drift from the code.
FAKE_EXECUTION = ExecutionResult(
    text="Implementei o desenho inteiro na skill e atualizei o SKILL.md, mas **não consegui rodar nada**: o sandbox "
         "pediu aprovação para todo comando Python.\n\n- **Aprendizados:** antes de repetir, busca os que servem.\n"
         "- **Estilos:** três fixos e versionados, direto, passo-a-passo e exemplo.\n- **Feedback:** tira um ponto do "
         "estilo criticado e abre as três opções.\n- **Escolha:** dá um ponto ao estilo escolhido.\n\n"
         "## O processo agora\n\n```mermaid\nflowchart LR\n  E[Task Explained] --> U[Learning Used] --> T[Taught Back]\n"
         "  T -->|ajuste| L[Learning Recorded] --> U\n  T -->|não ficou bom| F[Feedback] --> O[3 opções] --> C[Escolha]\n"
         "  C -->|score| S[Style Scored]\n  F -->|downscore| S\n```",
    method=Method.PRINT, harness=Harness.CLAUDE_CODE, model=Model.SONNET, effort=Effort.MEDIUM,
    cycle_time_s=87, delivery=Delivery.PR_CLOSED,
    session=SessionRef(Harness.CLAUDE_CODE, None, "~/.local/state/tasks-execute-b77a.log"),
    pull_request=PullRequest(41, "https://github.com/biliboss/skills/pull/41", PullRequestState.MERGED),
    commits=(Commit("99769cd", "feat(task-understand): 0.5.1, the whole process by the executor's first real run",
                    "biliboss/skills"),),
    before_afters=(
        BeforeAfter("O processo",
                    Picture(_mock("Antes", ["Task Explained", "Understanding Taught Back"], "#737373"),
                            "A tarefa só podia ser explicada e repetida"),
                    Picture(_mock("Depois", ["Task Explained", "Understanding Taught Back", "Feedback Given → 3 opções",
                                             "Style Scored"]), "Agora o feedback abre três opções com estilo")),
        BeforeAfter("A tarefa no estado",
                    Picture(_mock("Antes", ["id, title, text", "teach_backs, learnings, result"], "#737373"),
                            "Sem opções nem estilo"),
                    Picture(_mock("Depois", ["id, title, text", "teach_backs, learnings, result", "options, style"]),
                            "A tarefa guarda as opções e o estilo")),
    ),
    journeys=(
        Journey("Do feedback à escolha", (
            Picture(_mock("1 · Explicação", ["“Implementar todo o desenho do Tasks…”"]), "Você explica a tarefa"),
            Picture(_mock("2 · Repetição", ["“Implementar na skill todo o processo…”"]), "O agente repete do jeito que entendeu"),
            Picture(_mock("3 · Três opções", ["direto", "passo-a-passo", "exemplo"]), "Não ficou bom: três opções, uma por estilo"),
        )),
    ),
)
FAKE_TASK, FAKE_AT = "Implementar todo o desenho do Tasks na skill e atualizar o SKILL.md", "2026-11-05T10:46:15Z"

# How each typed value reads for a person
LABEL = {Method.PRINT: "Execução de uma vez", Method.INTERACTIVE: "Sessão interativa", Method.BY_HAND: "À mão, pelo agente",
         Harness.CLAUDE_CODE: "Claude Code", Harness.HERMES: "Hermes", Harness.PI: "pi",
         Model.SONNET: "Sonnet", Model.OPUS: "Opus", Model.HAIKU: "Haiku",
         Effort.LOW: "baixo", Effort.MEDIUM: "médio", Effort.HIGH: "alto",
         Delivery.PR_OPEN: "PR aberto", Delivery.PR_CLOSED: "PR fechado", Delivery.MAIN: "direto na main"}


def _result(ctx) -> tuple[ExecutionResult | None, dict | None]:
    """The selected task's real ExecutionResult and its event; (None, event) for a run that recorded only its text;
    the design's example only when the journal has no run at all."""
    run = _executed(ctx)
    if run:
        return result_from(run["value"]), run
    return FAKE_EXECUTION, None


def _src(src: str) -> str:
    """A picture kept with the task (media:<path>) is served by the tasks domain; data URIs and URLs pass as they are."""
    return f"/domain/tasks/media?f={src[6:]}" if src.startswith("media:") else src


def _duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m} min {s} s" if m else f"{s} s"


def _figure(pic: Picture, label: str = "", wide: bool = True):
    return Figure(Div(label, cls="text-[11px] uppercase tracking-widest text-neutral-400") if label else "",
                  Img(src=_src(pic.src), alt=pic.caption, cls="mt-1 w-full rounded border border-neutral-200 dark:border-neutral-800"),
                  Figcaption(pic.caption, cls="mt-1 text-sm text-neutral-500"),
                  cls="" if wide else "w-[220px] shrink-0 cursor-zoom-in", **({} if wide else {"data_media": "1"}))


def _with_media(*children, **kw):
    """Content whose diagrams and pictures open fullscreen; the arrows walk through all of them, in order."""
    return Div(Div(*children, **kw), Script(MEDIA_JS))


def before_after(ctx, standalone: bool = True):
    """Before and After: N comparisons, each a picture of how it was beside one of how it is; a click opens it fullscreen."""
    r = _result(ctx)[0]
    pairs = r.before_afters if r else ()
    body = [Div(P(ba.title, cls="mt-4 font-sans text-sm font-semibold text-neutral-700 dark:text-neutral-300"),
                Div(_figure(ba.before, "Antes"), _figure(ba.after, "Depois"),
                    cls="mt-2 grid grid-cols-2 gap-4 cursor-zoom-in", data_media="1")) for ba in pairs]
    content = Div(_title("Antes e depois"), *body) if pairs else Div(_title("Antes e depois"), P("nenhum", cls="text-neutral-400"))
    return _with_media(content) if standalone else content


def journey(ctx, standalone: bool = True):
    """Journey: N journeys, each the steps of the work as a row of pictures in order; a click opens them fullscreen."""
    r = _result(ctx)[0]
    js = r.journeys if r else ()
    body = [Div(P(j.title, cls="mt-4 font-sans text-sm font-semibold text-neutral-700 dark:text-neutral-300"),
                Div(*[_figure(pic, wide=False) for pic in j.steps], cls="mt-2 flex gap-3 overflow-x-auto pb-2")) for j in js]
    content = Div(_title("Jornada"), *body) if js else Div(_title("Jornada"), P("nenhuma", cls="text-neutral-400"))
    return _with_media(content) if standalone else content


before_after.fake = journey.fake = True  # designs on the value object, with example data


def _report(md: str):
    """The execution's text for people: markdown with headings, and fenced mermaid diagrams as media."""
    import re

    from monsterui.all import render_md

    out, last = [], 0
    for m in re.finditer(r"```mermaid\n(.*?)```", md, re.S):
        out.append(NotStr(render_md(md[last:m.start()])))
        out.append(Pre(m.group(1).strip(), cls="mermaid my-4 !bg-transparent cursor-zoom-in", data_media="1"))
        last = m.end()
    out.append(NotStr(render_md(md[last:])))
    return Div(*out, cls=f"report {BODY} [&_strong]:font-semibold [&_ul]:my-2 [&_ul]:pl-5 [&_li]:my-1")


MEDIA_JS = """
(() => {
  const root = document.currentScript.previousElementSibling; if (!root) return;
  root.querySelectorAll('.report h2').forEach(h => h.className = 'mt-8 mb-2 font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100');
  root.querySelectorAll('.report p').forEach(p => p.className = 'my-2');
  // the markdown renderer's own list classes give a second marker and a bigger font: one marker, the body's size
  root.querySelectorAll('.report ul').forEach(u => u.className = 'my-2 pl-5 list-disc');
  root.querySelectorAll('.report ol').forEach(u => u.className = 'my-2 pl-5 list-decimal');
  root.querySelectorAll('.report li').forEach(l => l.className = 'my-1');
  const go = () => window.mermaid ? window.mermaid.run({nodes: root.querySelectorAll('pre.mermaid:not([data-processed])')}) : setTimeout(go, 200);
  go();
  const items = () => [...root.querySelectorAll('[data-media]')];
  let lb = document.getElementById('media-lb');
  if (!lb) {
    lb = document.createElement('div'); lb.id = 'media-lb';
    lb.className = 'hidden fixed inset-0 z-[10050] bg-black/90 flex-col';
    lb.innerHTML = '<div class="flex items-center justify-between px-5 h-12 text-neutral-400 text-sm font-mono"><span id="media-n"></span>'
      + '<span>← → navegar · Esc fechar</span><button id="media-x" class="text-neutral-300 text-lg">✕</button></div>'
      + '<div class="relative flex-1 min-h-0 flex items-center justify-center px-16 pb-10">'
      + '<button id="media-prev" class="absolute left-4 text-4xl text-neutral-400 hover:text-white">‹</button>'
      + '<div id="media-stage" class="max-w-full max-h-full overflow-auto [&_img]:max-h-[74vh] [&_img]:mx-auto [&_svg]:max-h-[78vh] [&_svg]:mx-auto [&_figcaption]:text-neutral-300 [&_figcaption]:text-center"></div>'
      + '<button id="media-next" class="absolute right-4 text-4xl text-neutral-400 hover:text-white">›</button></div>';
    document.body.appendChild(lb);
    document.getElementById('media-x').onclick = () => { lb.classList.add('hidden'); lb.classList.remove('flex'); };
    document.getElementById('media-prev').onclick = () => lb.show(+lb.dataset.at - 1);
    document.getElementById('media-next').onclick = () => lb.show(+lb.dataset.at + 1);
    document.addEventListener('keydown', e => {
      if (lb.classList.contains('hidden')) return;
      if (e.key === 'ArrowRight') lb.show(+lb.dataset.at + 1);
      else if (e.key === 'ArrowLeft') lb.show(+lb.dataset.at - 1);
      else if (e.key === 'Escape') document.getElementById('media-x').click();
      else return;
      e.preventDefault(); e.stopImmediatePropagation(); }, true);
  }
  const open = i => { const all = items(); if (!all.length) return; lb.dataset.at = String((i + all.length) % all.length);
    const el = all[+lb.dataset.at].cloneNode(true); el.classList.remove('cursor-zoom-in', 'w-[220px]', 'my-4'); el.removeAttribute('data-media');
    document.getElementById('media-stage').replaceChildren(el);
    document.getElementById('media-n').textContent = `${+lb.dataset.at + 1} / ${all.length}`;
    lb.classList.remove('hidden'); lb.classList.add('flex'); };
  root.addEventListener('click', e => { const m = e.target.closest('[data-media]'); if (m && root.contains(m)) { lb.show = open; open(items().indexOf(m)); } });
})();
"""


def task_execution_result(ctx):
    """Task Execution Result: how the task was executed and what it delivered, drawn from ExecutionResult."""
    x, run = _result(ctx)
    fact = lambda label, value: Div(Div(label, cls="text-[11px] uppercase tracking-widest text-neutral-400"),  # noqa: E731
                                    Div(value, cls="mt-0.5 font-sans text-[15px] text-neutral-900 dark:text-neutral-100"))
    head = [_title("Resultado da execução"),
            P((ctx.state or {}).get("title") or FAKE_TASK, cls="font-sans text-sm text-neutral-500 dark:text-neutral-400")]
    if x is None:  # an older run: only its text was recorded
        return _with_media(*head, Div(_report(run["value"].get("text", "")), cls="mt-4"),
                           P(f"{_when(run['at'])} · execução antiga: só o relato foi registrado", cls="mt-4 text-xs text-neutral-400"),
                           cls="max-w-[760px]")
    pr = x.pull_request
    delivery = Span(LABEL[x.delivery], A(f" · #{pr.number}", href=pr.url, target="_blank",
                                         cls="text-neutral-500 underline decoration-neutral-400/50")) if pr else LABEL[x.delivery]
    example = run is None
    return _with_media(
        *head,
        Div(fact("Método", LABEL[x.method]), fact("Harness", LABEL[x.harness]), fact("Modelo", LABEL[x.model]),
            fact("Esforço", LABEL[x.effort]), fact("Cycle time", _duration(x.cycle_time_s)), fact("Entrega", delivery),
            cls="mt-4 grid grid-cols-3 gap-x-6 gap-y-3 py-4 border-y border-neutral-200 dark:border-neutral-800"),
        Div(_report(x.text), cls="mt-4"),
        P(_when(run["at"] if run else FAKE_AT), cls="mt-4 text-xs text-neutral-400"),
        # the parts, composed (never copied), each only when the run brought it
        Div(before_after(ctx, standalone=False), cls="mt-8") if x.before_afters else "",
        Div(journey(ctx, standalone=False), cls="mt-8") if x.journeys else "",
        Div(domain_diff(ctx, standalone=False), cls="mt-8") if example else "",
        P("dados de exemplo no value object ExecutionResult: o desenho vem antes da conexão", cls="mt-6 text-xs text-neutral-400")
        if example else "",
        cls="max-w-[760px]",
    )


task_execution_result.fake = True  # a design on fake data


# Design first: what the run of task b77a228e changed in the domain, as a diff of the Code tab's pseudo-code.
FAKE_DOMAIN_DIFF = [
    (" ", "Task.explain(value) -> Task.Explained"),
    (" ", ""),
    (" ", "class Task:  # the aggregate root, folded by the projector"),
    ("-", "    id, title, text, teach_backs, learnings, result, status, updated_at"),
    ("+", "    id, title, text, teach_backs, learnings, result, status, updated_at, options, style"),
    (" ", "    def explain(value) -> Task.Explained"),
    (" ", "    def execute(value) -> Task.Executed"),
]


def domain_diff(ctx, standalone: bool = True):
    """Domain Diff: what the execution changed in the domain, as a diff of the Code pseudo-code (sibling of Code)."""
    mark = {"+": "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
            "-": "bg-rose-500/10 text-rose-800 dark:text-rose-300 line-through decoration-rose-400/50",
            " ": "text-neutral-600 dark:text-neutral-400"}
    lines = [Div(Span(sign if sign != " " else "", cls="w-6 shrink-0 select-none text-center opacity-70"),
                 Span(code or "\u00a0", cls="min-w-0 whitespace-pre-wrap"), cls=f"flex px-2 {mark[sign]}")
             for sign, code in FAKE_DOMAIN_DIFF]
    added = sum(1 for x, _ in FAKE_DOMAIN_DIFF if x == "+")
    removed = sum(1 for x, _ in FAKE_DOMAIN_DIFF if x == "-")
    return Div(
        _title("Mudança no domínio"),
        P(f"pseudo-código · antes e depois da execução · +{added} −{removed}", cls="text-xs text-neutral-400"),
        Div(*lines, cls="mt-3 py-2 rounded border border-neutral-200 dark:border-neutral-800 font-mono text-[13px] leading-6"),
        P("dados de exemplo: o desenho vem antes da conexão", cls="mt-6 text-xs text-neutral-400") if standalone else "",
        cls="max-w-[760px]",
    )


domain_diff.fake = True  # a design on fake data


def task_execution_log(ctx):
    """Task Execution Log: the traces of the run for agents, session to resume, log, pull request and commits."""
    x = FAKE_EXECUTION
    row = lambda k, v: Div(Span(k, cls="w-32 shrink-0 text-neutral-400"), Span(v, cls="min-w-0 break-all"),  # noqa: E731
                           cls="flex gap-3 py-1 font-mono text-xs")
    pr = x.pull_request
    return Div(
        _title("Registro da execução"),
        row("harness", x.harness.value), row("método", x.method.value), row("modelo", f"{x.model.value} · {x.effort.value}"),
        row("cycle time", f"{x.cycle_time_s} s"),
        row("sessão", x.session.id or "sem id (rodou antes da saída JSON)"), row("log", x.session.log),
        row("pull request", f"#{pr.number} {pr.state.value} · {pr.url}") if pr else row("pull request", "nenhum"),
        *[row("commit", f"{c.sha} {c.repo} · {c.message}") for c in x.commits],
        P("dados de exemplo no value object ExecutionResult", cls="mt-6 text-xs text-neutral-400"),
        cls="max-w-[760px]")


task_execution_log.fake = True  # a design on the value object


def tasks(ctx):
    """Task Results: the executed tasks of a domain, the Task List beside the result of the selected one."""
    some = any(t.get("status") == "executed" and (not ctx.domain or t.get("domain") == ctx.domain)
               for t in ctx.entities)
    return Div(
        _title("Task Results"),
        Div(
            Div(task_list(ctx), cls="w-[320px] shrink-0 pr-4 border-r border-neutral-200 dark:border-neutral-800 overflow-y-auto"),
            Div(task_execution_result(ctx), cls="min-w-0 flex-1 pl-6 overflow-y-auto") if some else "",
            cls="flex " + ("h-[calc(100vh-9rem)]" if ctx.domain else "h-[66vh]")),
        cls="w-full" if ctx.domain else "w-[min(1100px,90vw)]",
    )


# the parts to show in the right menu's tree (not every composed widget, only the ones worth seeing)
tasks.parts = [task_list, task_execution_result]
task_execution_result.parts = [before_after, journey, domain_diff]

WIDGETS: dict = {
    "task.executed": [task_list, task_execution_result, before_after, journey, domain_diff, task_execution_log, tasks],
    "task.explained": [skill],
}
