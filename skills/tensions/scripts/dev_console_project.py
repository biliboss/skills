"""Tensions as a dev-console project: what the console needs to show this project.

Run: uv run --script ../../dev-console/scripts/dev-console.py --project scripts/dev_console_project.py
The console imports this file; fasthtml comes from the console's own environment.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from app_tensions import Tensions  # noqa: E402
from fasthtml.common import Button, Summary, Details, Script, Style, Div, Li, P, Span, Ul  # noqa: E402

NAME = "Tensions"
SOURCE = Path(__file__).parent / "app_tensions.py"  # the file with the command registry, EVENTS
ENTITY = "Tension"                                   # what one item of the rail is
ENTITY_PLURAL = "tensões"
ENTITIES = {"management": "Tension", "observation": "Observation", "relationship": "Relationship", "action": "Action"}
ENTITY_KEY = "tension_id"                            # the journal field that names the entity
BASE = ""                                            # set by the console: /domain/<slug>
PROJECTOR = "_project"                               # function that folds events into the entity (its dict literal = the properties)
journal = Tensions()


def title_of(history: list[dict], state: dict) -> str:
    created = next((e for e in history if e["event"] == "management.created"), None)
    return (created or {}).get("value", {}).get("title") or state.get("actual", "")


# --- widgets: event -> views. Each takes the console's EventContext (ctx) and returns a component. ---

def when(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")


def field(label: str, value: Any):
    return Div(Span(label, cls="w-24 shrink-0 text-neutral-400"),
               Span(str(value), cls="min-w-0 font-sans text-sm text-neutral-800 dark:text-neutral-200"),
               cls="flex gap-3 py-1")


def tension_list(ctx):
    """Every Tension in the journal; the current one marked."""
    return Ul(*[
        Li(Span("●" if t["id"] == ctx.entity_id else "○", cls="w-4 shrink-0 text-neutral-500"),
           Div(P(t.get("title") or t["actual"], cls="truncate font-sans text-sm "
                 + ("font-semibold text-neutral-900 dark:text-neutral-100" if t["id"] == ctx.entity_id
                    else "text-neutral-600 dark:text-neutral-400")),
               P(f'{t["status"]} · {t["event_count"]} eventos · {when(t["updated_at"])}', cls="text-neutral-400"),
               cls="min-w-0"),
           cls="flex gap-2 py-1.5")
        for t in sorted(ctx.entities, key=lambda t: t["updated_at"], reverse=True)
    ])


def tension_detail(ctx):
    """The Tension: the gap, the proposals up front (ProposalList), the observations folded below (ObservationList)."""
    s = ctx.state
    k = "text-[11px] uppercase tracking-widest text-neutral-500"
    big = "mt-1 font-sans text-[15px] leading-6 text-neutral-900 dark:text-neutral-100"
    obs = ctx.of("observation.recorded")
    props = ctx.of("action.proposed")
    n_obs = sum(e["value"].get("audience") == "human" for e in obs.events)
    keep = ("var u=new URL(location);this.open?u.searchParams.set('dt','obs'):u.searchParams.delete('dt');"
            "history.replaceState(null,'',u)")
    return Div(
        Div(Div(P("Hoje", cls=k), P(s["actual"], cls=big)),
            Div(P("Desejado", cls=k), P(s["desired"], cls=big)),
            cls="grid grid-cols-2 gap-8"),
        Div(P("O que fazer", cls="font-sans text-lg font-semibold text-neutral-900 dark:text-neutral-100"),
            Div(proposal_list(props), cls="mt-1"),
            cls="mt-8 pt-6 border-t border-neutral-200 dark:border-neutral-800"),
        Details(Summary(f"Observações · {n_obs}", cls="cursor-pointer font-sans text-sm text-neutral-500"),
                Div(observation_list(obs), cls="mt-2"),
                ontoggle=keep, cls="mt-8 pt-4 border-t border-neutral-200 dark:border-neutral-800"),
        Script("(function(){if(new URL(location).searchParams.get('dt')==='obs')"
               "document.querySelectorAll('[data-detail] details').forEach(function(d){d.open=true})})()"),
        data_detail="1",
    )


def tension_updates(ctx):
    """Each update: what changed and why."""
    return Ul(*[
        Li(P(f'{when(e["at"])} · {e["actor"]}', cls="text-neutral-400"),
           *[field(k, e["value"][k]) for k in ("actual", "desired", "context") if k in e["value"]],
           P(e["value"].get("reason", ""), cls="text-neutral-500"), cls="py-2")
        for e in reversed(ctx.events)
    ])


def observation_list(ctx):
    """What was seen about this Tension, for a human: the sentence, where, when, who."""
    line = "border-neutral-200 dark:border-neutral-800"
    human = [e for e in reversed(ctx.events) if e["value"].get("audience") == "human"]
    if not human:
        return P("Nenhuma observação escrita para gente ainda (audience: human).", cls="text-neutral-400")
    return Div(
        P(f"{len(human)} observações · {len(ctx.events) - len(human)} só para agentes", cls="pb-3 text-neutral-400 border-b " + line),
        *[Div(P(e["value"]["value"], cls="font-sans text-[15px] leading-6 text-neutral-900 dark:text-neutral-100"),
              P(when(e["value"].get("observed_at", e["at"])), cls="mt-0.5 text-neutral-400"),
              cls=f"py-3 border-b {line} last:border-0")
          for e in human],
    )


def observation_log(ctx):
    """Every observation, for agents too: raw text, source and time."""
    return Ul(*[
        Li(P(e["value"].get("value") or e["value"].get("observation", ""), cls="font-sans text-sm text-neutral-800 dark:text-neutral-200"),
           P(f'{e["value"].get("source", e["actor"])} · {when(e["value"].get("observed_at", e["at"]))}', cls="text-neutral-400"),
           cls="py-2 border-b border-neutral-100 dark:border-neutral-900 last:border-0")
        for e in reversed(ctx.events)
    ])


def linked_items(ctx):
    """What this Tension is linked to."""
    return Ul(*[
        Li(Span(e["value"]["target"], cls="w-20 shrink-0 font-semibold"),
           Span(e["value"].get("title", ""), cls="min-w-0 truncate font-sans text-sm text-neutral-700 dark:text-neutral-300"),
           cls="flex gap-3 py-1")
        for e in ctx.events
    ])


def proposal_list(ctx):
    """The proposed actions, each with a title for humans and the button that sends it to Bili local."""
    line = "border-neutral-200 dark:border-neutral-800"
    if not ctx.events:
        return P("Nenhuma proposta ainda.", cls="text-neutral-400")
    gone = {i for e in ctx.events for i in e["value"].get("supersedes", [])}  # a proposal may replace older ones
    rows = []
    for n, e in enumerate([e for e in ctx.events if e["id"] not in gone], 1):
        v = e["value"]
        title = v.get("title") or v.get("proposal", "")
        subtitle = v.get("subtitle") or (v.get("proposal", "") if v.get("title") else "")
        rows.append(Div(
            Span(f"{n}", cls="w-5 shrink-0 pt-0.5 tabular-nums text-neutral-400"),
            Div(P(title, cls="font-sans text-[15px] font-semibold leading-6 text-neutral-900 dark:text-neutral-100"),
                P(subtitle, cls="mt-0.5 font-sans text-sm leading-5 text-neutral-500") if subtitle else None,
                P(when(e["at"]), cls="mt-1 text-neutral-400"),
                ctx.expected(v.get("expected")),
                Div(id=f"run-{e['id']}"),
                cls="min-w-0 flex-1"),
            Button("Executar no Bili local", hx_post=f"{BASE}/do/{e['id']}/bili_local?mode={ctx.mode}",
                   hx_target=f"#run-{e['id']}", hx_swap="innerHTML", hx_on__after_request="this.remove()",
                   hx_confirm=("[simulado] " if ctx.mode == "sim" else "") + f"Mandar ao Bili local: {title}?",
                   cls="shrink-0 px-3 h-8 rounded bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 "
                       "font-sans text-sm hover:opacity-90"),
            cls=f"flex items-start gap-3 py-4 border-b {line} last:border-0"))
    return Div(*rows)


def _bili_message(event: dict) -> str:
    v = event["value"]
    return (f"tensions {event['tension_id'][:8]} · executar a proposta {event['id'][:8]}: "
            f"{v.get('title') or v.get('proposal', '')}. {v.get('proposal', '')} "
            f"Ao começar, grave action.started com proposal_id={event['id']}; ao terminar, action.completed "
            f"com o outcome (skill tensions).")


SIM_STEPS = [  # what a person sees after clicking, in order; each line is what really happens in REAL mode
    ("Enviada ao Bili local", "a tarefa entrou no pane H00 do herdr"),
    ("Bili local começou", "grava action.started ligado a esta proposta"),
    ("Bili local terminou", "grava action.completed com o resultado"),
]


def _timeline(done: int, live: bool):
    """The steps so far: done ones in full weight, the current one pulsing."""
    rows = []
    for i, (what, how) in enumerate(SIM_STEPS):
        if i > done:
            break
        on = i == done and live
        rows.append(Div(
            Span("●" if i < done or not live else "○", cls="w-4 shrink-0 " + ("animate-pulse" if on else "")),
            Span(what, cls="font-sans text-sm " + ("text-neutral-500" if on else "font-semibold text-neutral-900 dark:text-neutral-100")),
            Span(how, cls="text-neutral-400"),
            cls="flex items-baseline gap-2 py-0.5"))
    return Div(*rows)


def bili_local(event: dict, mode: str = "real", step: int = 0):
    """Send one proposal to Bili local (the herdr pane labelled H00): it starts the work and records
    action.started / action.completed with proposal_id. mode=sim plays the same experience without
    sending or writing anything. Returns what fills the proposal's run slot."""
    import json
    import subprocess

    from fasthtml.common import Details, Pre, Summary

    v = event["value"]
    msg = _bili_message(event)
    box = "mt-3 rounded border border-neutral-300 dark:border-neutral-700 px-3 py-2.5"
    if mode == "sim":
        last = len(SIM_STEPS) - 1
        nxt = dict(hx_get=f"{BASE}/do/{event['id']}/bili_local?mode=sim&step={step + 1}",
                   hx_trigger="load delay:1400ms", hx_target="this", hx_swap="outerHTML") if step < last else {}
        extra = []
        if step == 0:
            extra.append(Details(Summary("a mensagem que o H00 recebe", cls="cursor-pointer text-neutral-500"),
                                 P(msg, cls="mt-1 font-sans text-sm text-neutral-600 dark:text-neutral-400")))
        if step >= last:
            spec = dict(v.get("expected") or {})
            if spec:
                spec["heading"] = "Resultado"; spec["title"] = "simulado"
                extra.append(Div(render_expected(spec)))  # given by the console (see project-contract)
            would = [{"event": "action.started", "value": {"proposal_id": event["id"]}},
                     {"event": "action.completed", "value": {"proposal_id": event["id"], "outcome": "…"}}]
            extra.append(Details(Summary("o que entraria no diário", cls="cursor-pointer text-neutral-500"),
                                 Pre("\n".join(json.dumps(w, ensure_ascii=False) for w in would),
                                     cls="mt-1 whitespace-pre-wrap text-neutral-500")))
            extra.append(P("Simulação: nada foi enviado nem gravado.", cls="mt-2 text-neutral-400"))
        return Div(_timeline(step, live=step < last), *extra, cls=box, **nxt)
    panes = json.loads(subprocess.run(["herdr", "pane", "list"], capture_output=True, text=True, check=True).stdout)
    pane = next((p["pane_id"] for p in panes["result"]["panes"] if p.get("label", "").startswith("H00")), None)
    if not pane:
        return P("H00 não está aberto no herdr", cls="mt-3 text-neutral-500")
    subprocess.run(["herdr", "pane", "send-text", pane, msg], check=True)
    subprocess.run(["herdr", "pane", "send-keys", pane, "Enter"], check=True)
    return Div(_timeline(0, live=False), P("O andamento aparece aqui quando o Bili gravar action.started.",
                                           cls="mt-1 text-neutral-400"), cls=box)


ACTIONS = {"bili_local": bili_local}


# --- dummy widgets a proposal brings for its expected output (example data, real when the work is done) ---

def posthog_arrivals(data: dict):
    """The product events arriving in PostHog, per event, in the last hours."""
    rows = data.get("events", [])
    top = max((n for _, n in rows), default=1) or 1
    return Div(
        P(data.get("headline", ""), cls="font-sans text-sm text-neutral-800 dark:text-neutral-200"),
        *[Div(Span(name, cls="w-44 shrink-0 truncate"),
              Div(Div(cls="h-2 rounded bg-neutral-800 dark:bg-neutral-200", style=f"width:{100 * n / top:.0f}%"),
                  cls="flex-1"),
              Span(str(n), cls="w-10 shrink-0 text-right tabular-nums text-neutral-500"),
              cls="flex items-center gap-3 py-0.5")
          for name, n in rows],
        cls="space-y-1",
    )


EXPECTED_WIDGETS = {"PostHogArrivals": posthog_arrivals}

HOME = ("management.created", "TensionDetail")   # the widget the Visão tab opens with


WIDGETS = {
    "management.created": [tension_list, tension_detail],
    "management.updated": [tension_updates],
    "observation.recorded": [observation_list, observation_log],
    "relationship.linked": [linked_items],
    "action.proposed": [proposal_list],
}
