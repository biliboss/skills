"""Kanban in the dev-console: the owner's board, the console's home (its Quadro module opens at /).

Run: uv run --script ../../dev-console/scripts/dev-console.py --project scripts/dev_console_project.py
The console imports this file; fasthtml comes from the console's own environment. The widgets only draw the value
objects kanban.py computes (Board, CardMoney, UpstreamTotals): no number is computed here.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fasthtml.common import H2, Div, P, Script, Span  # noqa: E402
from kanban import (TRANSITIONS, Board, CardMoney, Column, KanbanJournal, Stage, UpstreamTotals, brl,  # noqa: E402,F401
                    card_from, hm, read_board, read_card, stage_age)

NAME = "Biliboss Skills - Kanban"
SLUG = "kanban"
BASE = ""  # set by the console: /domain/kanban
SOURCE = Path(__file__).parent / "kanban.py"  # the file with EVENTS
ENTITY = "Card"
ENTITY_PLURAL = "cards"
ENTITIES = {"card": "Card"}
ENTITY_KEY = "card_id"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"  # the house's own work: an investment center, priced at the goal

journal = KanbanJournal()

# The Human puts a card on the board.
INITIAL = ["card.created"]
# The Quadro is a module of this domain (⌘P lists it), drawn by the Board widget, and the console opens it at /.
TABS = ["Quadro"]
MODULE_WIDGETS = {"Quadro": ("card.created", "Board")}
CONSOLE_HOME = "Quadro"
# A click on a card opens the console's contextual sidebar: these widgets are its parts (then the card's JSON).
ENTITY_PARTS = {"Histórico": "CardHistory", "Tempo": "CardTime"}


def title_of(history: list[dict], state: dict) -> str:
    return state.get("title") or state.get("id", "")


# --- the look: the console's own (greys, mono, the 11px labels, the money bar's numbers) --------------------------
LABEL = "text-[11px] uppercase tracking-widest text-neutral-500"
LINE = "border-neutral-200 dark:border-neutral-800"
STRONG = "tabular-nums font-semibold text-neutral-800 dark:text-neutral-200"
DIM = "text-neutral-400"

# The money bar's way of ticking (dev-console MONEY_JS): a snapshot from the server and the R$ per hour it gains,
# redrawn every second. One timer for the page; it redraws whatever [data-tick-rate] is on screen.
TICK_JS = """
(() => {
  const brl = v => 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const hm = s => { const m = Math.floor(s / 60); return Math.floor(m / 60) + 'h' + String(m % 60).padStart(2, '0'); };
  const tick = () => document.querySelectorAll('[data-tick-rate]').forEach(el => {
    const rate = +el.dataset.tickRate; if (!rate) return;
    const dt = Math.max(0, (Date.now() - +el.dataset.tickAt) / 1000);
    el.querySelectorAll('[data-brl]').forEach(x => { x.textContent = brl(+x.dataset.brl + dt * rate / 3600); });
    el.querySelectorAll('[data-sec]').forEach(x => { x.textContent = hm(+x.dataset.sec + dt); });
  });
  if (!window.__kanbanTick) window.__kanbanTick = setInterval(tick, 1000);
  tick();
})();
"""


def _title(text: str):
    """Every widget starts with its title (in a module or a sidebar part the console hides it: the line names it)."""
    return H2(text, cls="mb-3 font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100")


def _when(t: datetime) -> str:
    return t.astimezone().strftime("%d/%m %H:%M")


def _ms(t: datetime) -> str:
    return str(int(t.timestamp() * 1000))


def _amount(seconds: float, money: float, rate: float, at: datetime, strong: bool = True):
    """R$ and hours, ticking at `rate` R$/h from `at` (0 = still)."""
    return Span(Span(brl(money), data_brl=f"{money:.2f}", cls=STRONG if strong else f"tabular-nums {DIM}"),
                Span("·", cls=DIM),
                Span(hm(seconds), data_sec=f"{seconds:.0f}", cls=f"tabular-nums {DIM}"),
                data_tick_rate=f"{rate:.6f}", data_tick_at=_ms(at), cls="flex items-baseline gap-1")


def _band(tot: UpstreamTotals):
    """The thin band on top of the Quadro: Upstream, then Hoje, Semana and Mês in R$ and hours."""
    live = (Span("●", title=f"o relógio está ligado em {tot.live_domain}: os números sobem a cada segundo",
                 cls="animate-pulse text-neutral-500") if tot.live_rate_hour else None)
    group = lambda label, m: Span(Span(label, cls="text-neutral-500"),  # noqa: E731
                                  _amount(m.seconds, m.brl, tot.live_rate_hour, tot.at), cls="shrink-0 flex items-baseline gap-1.5")
    # one thin line (it fits beside the open sidebar at two thirds of a screen); bigger numbers in a narrower window
    # wrap it, never clip it
    return Div(Span(Span("Upstream", cls=LABEL), live, cls="shrink-0 flex items-center gap-1.5"),
               group("Hoje", tot.today), group("Semana", tot.week), group("Mês", tot.month),
               data_band="1", cls=f"min-h-8 shrink-0 flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-1.5 "
                                  f"whitespace-nowrap border-b {LINE}")


def _card(m: CardMoney, now: datetime):
    """A card in its column: the title, what it cost in Upstream, its domain and how long it has been in the stage. A
    click (Enter, Space) opens the console's sidebar for it (data-entity)."""
    c = m.card
    age = stage_age((now - c.since).total_seconds())
    spent = bool(m.total.seconds or m.live_rate_hour)
    return Div(
        P(c.title, cls="font-sans text-sm leading-5 text-neutral-900 dark:text-neutral-100 [overflow-wrap:anywhere]"),
        Div(_amount(m.total.seconds, m.total.brl, m.live_rate_hour, now, strong=spent), cls="mt-1"),
        # the time in the stage first: in a narrow column only the domain is cut (the sidebar repeats both)
        P(f"{age} · {c.domain}", title=f"{age}, domínio {c.domain}", cls=f"mt-0.5 truncate {DIM}"),
        tabindex="0", data_entity=c.id, data_entity_name=c.title, data_entity_sub=f"{c.stage.value} · {age} · {c.domain}",
        aria_label=f"abrir {c.title}",
        cls="px-4 py-2.5 cursor-pointer border-b border-l-2 border-l-transparent border-b-neutral-100 dark:border-b-neutral-900 "
            "hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:outline-none focus-visible:bg-neutral-100 "
            "dark:focus-visible:bg-neutral-900")


def _column(col: Column, now: datetime):
    head = Div(Span(col.stage.value), Span(str(len(col.cards)), cls=f"tabular-nums {DIM}"),
               cls=f"h-9 shrink-0 flex items-center justify-between px-4 {LABEL} border-b {LINE}")
    cards = [_card(m, now) for m in col.cards] or [P("nenhum card", cls=f"px-4 py-3 {DIM}")]
    return Div(head, Div(*cards, cls="flex-1 min-h-0 overflow-y-auto"),
               data_stage=col.stage.value, cls=f"min-w-0 min-h-0 flex flex-col border-l {LINE} first:border-l-0")


# --- widgets: each starts with its title; real data only (both journals read now) ----------------------------------
def board(ctx):
    """Board: the Quadro, the Upstream money band on top and one column per stage, each card with its Upstream money."""
    b: Board = read_board()
    return Div(_title("Quadro"), _band(b.totals),
               # gap-0: Pico's .grid has a column gap of its own
               Div(*[_column(c, b.at) for c in b.columns], cls="flex-1 min-h-0 grid grid-cols-3 gap-0"),
               Script(TICK_JS),
               # a fresh snapshot every 10 s (a move by an agent, the clock started elsewhere) and at once when the money
               # bar starts, stops or enters on this page (devconsole-money); never while it is hidden
               hx_get=f"{BASE}/w/_/card.created/Board", hx_swap="outerHTML",
               hx_trigger="every 10s [this.offsetParent], devconsole-money from:document",
               data_board="1", cls="h-full min-h-[24rem] flex flex-col")


def upstream_band(ctx):
    """Upstream Band: what the cards' Upstream time cost today, this week (from Monday) and this month, ticking while
    the clock runs on the domain of a card in Upstream."""
    return Div(_title("Investido em Upstream"), _band(read_board().totals), Script(TICK_JS))


board.parts = [upstream_band]


def card_history(ctx):
    """Card History: the stages a card went through, each as a sentence with its time."""
    c = card_from(list(ctx.history))
    if c is None:
        return Div(_title("Histórico"), P("Nenhum card.", cls=DIM))
    rows = []
    for i, s in enumerate(c.stays):
        text = f"entrou no quadro em {s.stage.value}" if i == 0 else f"foi de {c.stays[i - 1].stage.value} para {s.stage.value}"
        rows.append(Div(Span(_when(s.start), cls=f"w-[5.5rem] shrink-0 tabular-nums {DIM}"),
                        Span(text, cls="min-w-0 font-sans text-sm text-neutral-800 dark:text-neutral-200"),
                        cls="flex items-baseline gap-3 py-1"))
    return Div(_title("Histórico"), *rows)


def card_time(ctx):
    """Card Time: the card's time in Upstream, each stretch of its domain's clock with its money, and the total."""
    now = datetime.now().astimezone()
    m = read_card(ctx.entity_id, now)
    if m is None:
        return Div(_title("Tempo em Upstream"), P("Nenhum card.", cls=DIM))
    grid = "grid grid-cols-[1fr_auto_auto] items-baseline gap-3"
    rows = []
    for s in m.slices:
        end = "agora" if s.running else s.end.astimezone().strftime("%H:%M")
        rate = m.live_rate_hour if s.running else 0.0
        rows.append(Div(Span(f"{_when(s.start)}–{end}", cls="tabular-nums text-neutral-600 dark:text-neutral-400"),
                        Span(hm(s.seconds), data_sec=f"{s.seconds:.0f}", cls=f"tabular-nums {DIM}"),
                        Span(brl(s.brl), data_brl=f"{s.brl:.2f}", cls=f"text-right {STRONG}"),
                        data_tick_rate=f"{rate:.6f}", data_tick_at=_ms(now), cls=f"{grid} py-0.5"))
    if not rows:
        return Div(_title("Tempo em Upstream"), P("Nenhum tempo em Upstream ainda.", cls=DIM))
    total = Div(Span("total", cls="text-neutral-500"),
                Span(hm(m.total.seconds), data_sec=f"{m.total.seconds:.0f}", cls=f"tabular-nums {DIM}"),
                Span(brl(m.total.brl), data_brl=f"{m.total.brl:.2f}", cls=f"text-right {STRONG}"),
                data_tick_rate=f"{m.live_rate_hour:.6f}", data_tick_at=_ms(now), cls=f"{grid} mt-1 pt-1 border-t {LINE}")
    return Div(_title("Tempo em Upstream"), *rows, total,
               P(f"Só o tempo do domínio {m.card.domain} enquanto o card esteve em Upstream, pelo preço da hora do "
                 "centro de custo.", cls=f"mt-2 font-sans {DIM}"),
               Script(TICK_JS))


WIDGETS = {
    "card.created": [board, upstream_band, card_history, card_time],
    "card.moved": [card_history],
}
HOME = ("card.created", "Board")
