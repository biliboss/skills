"""domain-plan, the dev-console side: the plan's drafts drawn with the console's own convention.

A project file imports this and adds the plan to what it already has; nothing new is drawn:

    import dev_console_plan as plan
    SOURCE = <the plan's console_source>                        # the real events file + the drafts, written by plan.sh
    TRANSITIONS = plan.with_edges(REAL_TRANSITIONS, PLAN_FILE)  # the drafts' `after` edges
    WIDGETS = {..., **plan.widgets(PLAN_FILE, WIDGETS)}         # Plano on every event, Tela on events with a screen

The console reads EVENTS from SOURCE with ast, so the drafts are written there (plan.py `sync`, after every change).
A draft event has no record in any journal, so the console outlines it (outlined = not in the code); an event the code
records is filled. A draft the real registry already has is not written twice, so a built draft is just filled.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan as P  # noqa: E402


def _state(plan_file):
    return P.project(P.read_events(Path(plan_file).expanduser()))


def with_edges(real: dict, plan_file) -> dict:
    out = {k: list(v) for k, v in real.items()}
    for (kind, name), el in _state(plan_file)["elements"].items():
        if kind == "event" and el.get("after") and name not in out.get(el["after"], []):
            out.setdefault(el["after"], []).append(name)
    return out


def widgets(plan_file, base: dict) -> dict:
    """{event: [..., plano, tela]}: Plano (the drift) on every event of the plan and the code; Tela where a screen sits."""
    from fasthtml.common import H2, Div, Iframe, P as Para

    plan_file = Path(plan_file).expanduser()

    def plano(ctx):
        """Plano: the drawing against the code (to build, built, unplanned)."""
        st = _state(plan_file)
        d = P.drift(st, plan_file.parent.parent)
        rows = [H2("Plano", style="font-size:18px;margin:0 0 8px")]
        for key, title in (("to_build", "A construir"), ("built", "Construído"), ("unplanned", "Fora do plano"), ("lost", "Perdido")):
            if d[key]:
                rows.append(Div(title, style="font-weight:600;margin:12px 0 4px"))
                rows += [Div(f"{i['kind']} · {i['name']}", style="font-size:14px;opacity:.8") for i in d[key]]
        for doc in d["documents"]:
            rows.append(Div(doc["name"], style="font-weight:600;margin:12px 0 4px"))
            rows += [Para(f"? {q}", style="font-size:14px;margin:2px 0") for q in doc["questions"]]
        return Div(*rows, data_real_only="1")

    def tela(ctx):
        """Tela: the real screen drawn above the event."""
        st = _state(plan_file)
        ev = getattr(ctx, "event", "")
        els = [e for (k, _), e in st["elements"].items() if k == "screen" and e.get("event") == ev]
        repo = plan_file.parent.parent
        frames = []
        for e in els:
            src = Path(repo / e["file"]).read_text(encoding="utf-8") if e.get("file") and (repo / e["file"]).exists() else None
            frames.append(Iframe(srcdoc=src, style="width:100%;height:520px;border:1px solid rgba(127,127,127,.3);border-radius:6px")
                          if src is not None else Iframe(src=e.get("url", ""), style="width:100%;height:520px;border:0"))
        return Div(H2("Tela", style="font-size:18px;margin:0 0 8px"), *(frames or [Para("sem tela desenhada para este evento")]),
                   data_real_only="1")

    # `fake` makes the console render a widget with no journal record (the plan is the data, not the journal), and
    # data-real-only hides REAL | SIMULADO: there is nothing to simulate in a widget read from the plan file.
    plano.fake = tela.fake = True

    events = set(base) | {n for (k, n) in _state(plan_file)["elements"] if k == "event"}
    return {ev: [*base.get(ev, []), plano, tela] for ev in events}
