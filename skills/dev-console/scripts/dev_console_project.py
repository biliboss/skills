"""The dev-console as a dev-console project: it shows the domains hooked into it, itself included.

Run: uv run --script scripts/dev-console.py --project scripts/dev_console_project.py
The journal is derived from code (ast), read-only; see console_domain.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from console_domain import ConsoleJournal  # noqa: E402
from fasthtml.common import Div, Iframe, Li, P, Span, Ul  # noqa: E402

NAME = "dev-console"
SLUG = "dev-console"
SOURCE = Path(__file__).parent / "console_domain.py"  # the file with EVENTS
ENTITY = "Domain"
ENTITY_PLURAL = "domínios"
ENTITIES = {"domain": "Domain", "event": "Event", "widget": "Widget", "tab": "Tab"}
ENTITY_KEY = "domain_id"
PROJECTOR = "_project"
journal = ConsoleJournal()
render_widget_list = None  # set by the console: the right menu's WidgetList, for composition

K = "text-[11px] uppercase tracking-widest text-neutral-500"
BODY = "font-sans text-sm text-neutral-800 dark:text-neutral-200"


def title_of(history: list[dict], state: dict) -> str:
    return state.get("name", "")


def widget_list(ctx):
    """The widgets of one event, each with abrir: the right menu's own WidgetList, composed (never a copy)."""
    if not ctx.focus:
        return P("Nenhum widget registrado.", cls="text-neutral-400")
    return render_widget_list(ctx.focus["domain_id"], ctx.focus["value"]["event"])


def event_list(ctx):
    """The event types this Domain declares, each with the command that records it."""
    if not ctx.events:
        return P("Nenhum evento declarado.", cls="text-neutral-400")
    return Ul(*[Li(Span(e["value"]["event"], cls="w-56 shrink-0 font-semibold text-neutral-900 dark:text-neutral-100"),
                   Span(e["value"]["command"], cls=BODY), cls="flex gap-3 py-1") for e in ctx.events])


def toolbar(ctx):
    """The domain's toolbar: the console's real tab bar, embedded (?embed=toolbar), never a copy of its markup."""
    slug = (ctx.focus or {}).get("domain_id", SLUG)
    sim = "&sim_tab=Eventos" if ctx.mode == "sim" else ""  # SIMULADO: an example tab from the context, nothing recorded
    return Iframe(src=f"/domain/{slug}?embed=toolbar{sim}",
                  cls="w-full h-11 rounded border border-neutral-200 dark:border-neutral-800")


# --- DomainView: the Domain's screen is the console's own Domain tab. The dev-console documents and builds itself:
# its screens are widgets of its own domain. The view embeds the Domain tab of the domain it shows (the graph, the
# sidebar and the popup, the same template), so there is one Domain screen, never a copy.
def domain_view(ctx):
    """The Domain tab itself: StateGraph plus the sidebar and popup a click opens."""
    slug = ctx.entity_id if ctx.focus else SLUG  # no designed domain recorded yet: the dev-console shows itself
    return Iframe(src=f"/domain/{slug}?tab=Domain&embed=1", cls="w-full h-[68vh] rounded border border-neutral-200 dark:border-neutral-800")


domain_view.fake = True  # a console screen: it renders before any event is recorded


def state_graph(ctx):
    """The state machine alone, drawn from the real code (EVENTS read with ast): Human, commands, events."""
    slug = ctx.entity_id if ctx.focus else SLUG
    return Iframe(src=f"/domain/{slug}?tab=Domain&embed=graph", cls="w-full h-[68vh] rounded border border-neutral-200 dark:border-neutral-800")


state_graph.fake = True  # drawn from code, so it exists before any event is recorded


def right_menu(ctx):
    """The right menu: a clicked event's sidebar, with its expandable parts (Widgets, Code, JSON, Observability)."""
    slug = SLUG  # ctx.event is an event of this domain (the dev-console's own), so its menu lives here
    return Iframe(src=f"/domain/{slug}?tab=Domain&embed=side&ev={ctx.event}",
                  cls="w-full h-[68vh] rounded border border-neutral-200 dark:border-neutral-800")


right_menu.fake = True  # a console screen: it exists before any event is recorded


def domain_switcher(ctx):
    """Switch domain: the console's real Domain Switcher (⌘K), a fuzzy search over an overlay, embedded."""
    return Iframe(src=f"/domain/{SLUG}?tab=Domain&embed=switcher",
                  cls="w-full h-[48vh] rounded border border-neutral-200 dark:border-neutral-800")


domain_switcher.fake = True  # a console screen: it exists before any event is recorded


def code(ctx):
    """The event's pseudo-code: the right menu's Code tab, embedded (never a copy)."""
    return Iframe(src=f"/domain/{SLUG}?tab=Domain&embed=code&ev={ctx.event}&side=Code",
                  cls="w-full h-[60vh] rounded border border-neutral-200 dark:border-neutral-800")


code.fake = True  # drawn from the code, so it exists before any event is recorded


HOME = ("domain.updated", "DomainView")
INITIAL = ["domain.designed", "domain.imported"]  # Human -> Domain.Designed (new) or Domain.Imported (existing)
HUB = "domain.updated"  # both starts lead to Domain.Updated, and it links every other category

WIDGETS = {
    # the Domain's widgets hang on Domain.Updated only: Designed and Imported are starts, with nothing to show
    "domain.updated": [domain_view, state_graph, right_menu, code, domain_switcher],
    "event.updated": [event_list],
    "widget.updated": [widget_list],
    "tab.updated": [toolbar],
}
