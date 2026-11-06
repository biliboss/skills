"""The dev-console as a dev-console project: it shows the domains hooked into it, itself included.

Run: uv run --script scripts/dev-console.py --project scripts/dev_console_project.py
The journal is derived from code (ast), read-only; see console_domain.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from console_domain import ConsoleJournal  # noqa: E402
from fasthtml.common import Div, Iframe, Li, NotStr, P, Span, Ul  # noqa: E402

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
BODY = "font-sans text-sm text-neutral-800"


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
    return Ul(*[Li(Span(e["value"]["event"], cls="w-56 shrink-0 font-semibold text-neutral-900"),
                   Span(e["value"]["command"], cls=BODY), cls="flex gap-3 py-1") for e in ctx.events])


def toolbar(ctx):
    """The domain's toolbar: the console's real status line, embedded (?embed=toolbar), never a copy of its markup."""
    slug = (ctx.focus or {}).get("domain_id", SLUG)
    sim = "&sim_tab=Eventos" if ctx.mode == "sim" else ""  # SIMULADO: an example module from the context, nothing recorded
    return Iframe(src=f"/domain/{slug}?embed=toolbar{sim}",
                  cls="w-full h-11 rounded border border-neutral-200")


# --- DomainView: the Domain's screen is the console's own Domain tab. The dev-console documents and builds itself:
# its screens are widgets of its own domain. The view embeds the Domain tab of the domain it shows (the graph, the
# sidebar and the popup, the same template), so there is one Domain screen, never a copy.
def domain_view(ctx):
    """The Domain tab itself: StateGraph plus the sidebar and popup a click opens."""
    slug = ctx.entity_id if ctx.focus else SLUG  # no designed domain recorded yet: the dev-console shows itself
    return Iframe(src=f"/domain/{slug}?tab=Domain&embed=1", cls="w-full h-[68vh] rounded border border-neutral-200")


domain_view.fake = True  # a console screen: it renders before any event is recorded


def state_graph(ctx):
    """The state machine alone, drawn from the real code (EVENTS read with ast): Human, commands, events."""
    slug = ctx.entity_id if ctx.focus else SLUG
    return Iframe(src=f"/domain/{slug}?tab=Domain&embed=graph", cls="w-full h-[68vh] rounded border border-neutral-200")


state_graph.fake = True  # drawn from code, so it exists before any event is recorded


def right_menu(ctx):
    """The right menu: a clicked event's sidebar, with its expandable parts (Widgets, Code, JSON, Observability)."""
    slug = SLUG  # ctx.event is an event of this domain (the dev-console's own), so its menu lives here
    return Iframe(src=f"/domain/{slug}?tab=Domain&embed=side&ev={ctx.event}",
                  cls="w-full h-[68vh] rounded border border-neutral-200")


right_menu.fake = True  # a console screen: it exists before any event is recorded


def domain_switcher(ctx):
    """Switch domain: the console's real Domain Switcher (⌘K), a fuzzy search over an overlay, embedded."""
    return Iframe(src=f"/domain/{SLUG}?tab=Domain&embed=switcher",
                  cls="w-full h-[48vh] rounded border border-neutral-200")


domain_switcher.fake = True  # a console screen: it exists before any event is recorded


def code(ctx):
    """The event's pseudo-code: the right menu's Code tab, embedded (never a copy)."""
    return Iframe(src=f"/domain/{SLUG}?tab=Domain&embed=code&ev={ctx.event}&side=Code",
                  cls="w-full h-[60vh] rounded border border-neutral-200")


code.fake = True  # drawn from the code, so it exists before any event is recorded


def logo(ctx):
    """The console's mark, the `</>` tag (tournament logo-devconsole): the one widget the Home starts with (table `home`)."""
    return Div(NotStr('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="96" height="96" aria-label="dev-console">'
                      '<path d="M4.82 4.25 L1.24 8.00 L4.82 11.75 M6.82 12.35 L9.18 3.65 M11.18 4.25 L14.76 8.00 L11.18 11.75" '
                      'fill="none" stroke="currentColor" stroke-width="1.70" stroke-linecap="round" stroke-linejoin="round"/></svg>'),
               cls="flex items-center justify-center")


logo.fake = True  # a mark: it renders before any event is recorded


HOME = ("domain.updated", "DomainView")
INITIAL = ["domain.designed", "domain.imported"]  # Human -> Domain.Designed (new) or Domain.Imported (existing)
HUB = "domain.updated"  # both starts lead to Domain.Updated, and it links every other category

WIDGETS = {
    # the Domain's widgets hang on Domain.Updated only: Designed and Imported are starts, with nothing to show
    "domain.updated": [domain_view, state_graph, right_menu, code, domain_switcher, logo],
    "event.updated": [event_list],
    "widget.updated": [widget_list],
    "tab.updated": [toolbar],
}
