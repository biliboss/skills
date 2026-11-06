"""Kanban in the dev-console: the owner's board, the console's home (its Quadro module opens at /).

Run: uv run --script ../../dev-console/scripts/dev-console.py --project scripts/dev_console_project.py
The console imports this file; fasthtml comes from the console's own environment. The widgets only draw the value
objects kanban.py computes (Board, CardMoney, UpstreamTotals): no number is computed here.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fasthtml.common import H2, Div, P, Script, Span  # noqa: E402
from kanban import (TRANSITIONS, Board, CardMoney, Column, KanbanJournal, Stage, UpstreamTotals, brl,  # noqa: E402,F401
                    card_from, hm, journal_path, read_board, read_card, stage_age)

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
ACCENT = "text-[#800020] dark:text-[#a3263f]"  # bordô: the one accent, only on what is moving (design-taste)

def LIVE_DIRS():
    """The folders whose writes the console pushes to open pages at once (the Kanban journal's)."""
    return [journal_path().parent]


WATCH = ["../../cost-track/scripts"]  # the console also watches cost-track's costs.py (read by kanban.py)


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


# The Quadro follows the Kanban journal by itself: every 2 s a tiny widget answers the journal's mtime, and when it
# differs from the one the board was drawn at, the board is fetched again (the server stays the source of truth).
WATCH_JS = """
(() => {
  const url = %r;
  if (window.__kanbanWatch) clearInterval(window.__kanbanWatch);
  window.__kanbanWatch = setInterval(async () => {
    const board = document.querySelector('[data-board]');
    if (!board || !board.offsetParent) return;
    try {
      const html = await (await fetch(url, {cache: 'no-store'})).text();
      const m = html.match(/data-stamp="([^"]*)"/);
      if (m && m[1] !== board.dataset.stamp && window.htmx) htmx.trigger(board, 'kanban-journal');
    } catch (e) {}
  }, 2000);
})();
"""


def _stamp() -> str:
    """The Kanban journal's modification time (ns): changes whenever any event is appended."""
    try:
        return str(journal_path().stat().st_mtime_ns)
    except OSError:
        return "0"


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
                 cls=f"animate-pulse {ACCENT}") if tot.live_rate_hour else None)
    group = lambda label, m: Span(Span(label, cls="text-neutral-500"),  # noqa: E731
                                  _amount(m.seconds, m.brl, tot.live_rate_hour, tot.at), cls="shrink-0 flex items-baseline gap-1.5")
    # one thin line (it fits beside the open sidebar at two thirds of a screen); bigger numbers in a narrower window
    # wrap it, never clip it
    return Div(Span(Span("Upstream", cls=LABEL), live, cls="shrink-0 flex items-center gap-1.5"),
               group("Hoje", tot.today), group("Semana", tot.week), group("Mês", tot.month),
               data_band="1", cls=f"min-h-8 shrink-0 flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-1.5 "
                                  f"whitespace-nowrap border-b {LINE}")


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


# The Hermes TUI status line: "─ ready │ opus 5.5 │ 25k/1M │ [░░░] 2% ─ …" (a narrow pane drops the %); anything but
# "ready" means it is working.
STATUS_RE = re.compile(r"─\s+(.+?)\s+│\s+([^│]+?)\s+│\s+([\d.]+[kKmM]?)/([\d.]+[kKmM]?)")
# Hermes asking for the owner while its status word stays "running…": the approval and clarify prompts of the TUI
# (ui-tui/src/components/prompts.tsx) draw these hints under their choices.
WAITING_RE = re.compile(r"↑/↓ select · Enter confirm|quick pick · Esc|\d+/\d+ answered ·")


def agent_state(card) -> dict | None:
    """The card's agent: the tmux session named like the card (slug of its title, then its domain) and the state its
    Hermes window shows: pronto, trabalhando or esperando você (a prompt waits for an answer). Read-only (tmux
    list/capture); None when the card has no session."""
    def tmux(*args: str) -> str:
        try:
            return subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=1).stdout
        except (OSError, subprocess.TimeoutExpired):
            return ""
    sessions = {line.split("\t")[0]: line.split("\t")[1:] for line in tmux(
        "list-sessions", "-F", "#{session_name}\t#{session_attached}\t#{session_activity}").splitlines() if "\t" in line}
    name = next((n for n in (_slug(card.title), _slug(card.domain)) if n in sessions), None)
    if name is None:
        return None
    attached, activity = sessions[name][0] != "0", int(sessions[name][1] or 0)
    screen = tmux("capture-pane", "-p", "-t", f"{name}:1")
    hit = next((m for m in map(STATUS_RE.search, reversed(screen.splitlines())) if m), None)
    if hit is None:
        state, ctx = "sem Hermes aberto", ""
    else:
        word = hit.group(1).strip()
        state = "esperando você" if WAITING_RE.search(screen) else "pronto" if word == "ready" else "trabalhando"
        ctx = f"contexto {hit.group(3)} de {hit.group(4)}"
    return {"session": name, "state": state, "context": ctx, "attached": attached, "activity": activity}


AGENT_MARK = {"trabalhando": "●", "esperando você": "◆", "pronto": "○", "sem Hermes aberto": "○"}


def _agent(card):
    """The third line of the card, only with a session: ● trabalhando (pulses), ◆ esperando você (the one bold state:
    it asks for the owner) or ○ pronto. The context and the session are in the tooltip."""
    a = agent_state(card)
    if a is None:
        return None
    s = a["state"]
    return P(Span(AGENT_MARK[s], cls="mr-1 " + (f"animate-pulse {ACCENT}" if s == "trabalhando" else "")), s,
             title=f"sessão {a['session']}: sesh connect {a['session']}" + (f" · {a['context']}" if a["context"] else ""),
             data_agent=s, cls=f"mt-0.5 truncate font-sans text-[14px] {'font-bold text-neutral-800 dark:text-neutral-200' if s == 'esperando você' else 'text-neutral-600 dark:text-neutral-400'}")


AGING_DAYS = 2  # a card this long in one stage ages (Kanban Method): its stage line turns bold


def _in_stage(seconds: float, stage: str) -> str:
    """Static, for a person: "há 3 min no Upstream" (the server draws it; the 10 s refresh updates it)."""
    s = int(max(seconds, 0))
    m, h = s // 60, s // 3600
    n = f"{s} s" if s < 60 else f"{m} min" if m < 60 else f"{h} h" if h < 24 else f"{h // 24} dia{'s' if h // 24 > 1 else ''}"
    return f"há {n} no {stage}"


def _clock(m: CardMoney, now: datetime):
    """The second line, the timer everyone knows: ▶ running (ticks), ⏸ paused (cost, still, gray), nothing for a card that
    never ran (dim)."""
    if m.live_rate_hour:
        return Div(Span("▶", cls=ACCENT), _amount(m.total.seconds, m.total.brl, m.live_rate_hour, now), cls=f"mt-1 flex items-baseline gap-1.5 {ACCENT} [&_*]:!text-inherit")
    paused = bool(m.total.seconds)
    return Div(Span("⏸", cls=DIM) if paused else None, _amount(m.total.seconds, m.total.brl, 0, now, strong=False),
               data_clock="paused" if paused else "never", cls="mt-1 flex items-baseline gap-1.5")


def _card(m: CardMoney, now: datetime):
    """A card in its column: the title, what it cost in Upstream, its domain and how long it has been in the stage, and
    the state of its agent when it has a session. A click (Enter, Space) opens the console's sidebar (data-entity)."""
    c = m.card
    secs = (now - c.since).total_seconds()
    age = _in_stage(secs, c.stage.value)
    return Div(
        P(c.title, cls="font-sans text-sm leading-5 text-neutral-900 dark:text-neutral-100 [overflow-wrap:anywhere]"),
        P(c.why, title=c.description, cls=f"mt-0.5 line-clamp-2 [overflow-wrap:anywhere] {DIM}") if c.why else None,
        _clock(m, now),
        _agent(c) if c.stage.value in ("Upstream", "Downstream") else None,
        # the time in the stage last and still: in a narrow column only the domain is cut (the sidebar repeats both)
        P(f"{age} · {c.domain}", title=f"{age}, domínio {c.domain}", data_aging="1" if secs >= AGING_DAYS * 86400 else None,
          cls=f"mt-0.5 truncate {'font-bold text-neutral-700 dark:text-neutral-300' if secs >= AGING_DAYS * 86400 else DIM}"),
        tabindex="0", data_entity=c.id, data_entity_name=c.title, data_entity_sub=f"{c.stage.value} · {stage_age(secs)} · {c.domain}",
        aria_label=f"abrir {c.title}",
        cls="px-4 py-2.5 cursor-pointer border-b border-l-2 border-l-transparent border-b-neutral-100 dark:border-b-neutral-900 "
            "hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:outline-none focus-visible:bg-neutral-100 "
            "dark:focus-visible:bg-neutral-900")


def _column(col: Column, now: datetime):
    # count/limit when the stage has a limit; over it the header is bold with a darker rule (grayscale, no red)
    over = col.limit is not None and len(col.cards) > col.limit
    count = f"{len(col.cards)}/{col.limit}" if col.limit else str(len(col.cards))
    head = Div(Span(col.stage.value), Span(count, cls=f"tabular-nums {'font-bold' if over else DIM}"),
               data_over="1" if over else None,
               cls=f"h-9 shrink-0 flex items-center justify-between px-4 {LABEL} border-b {'border-neutral-900 dark:border-neutral-100 font-bold' if over else LINE}")
    cards = [_card(m, now) for m in col.cards] or [P("nenhum card", cls=f"px-4 py-3 {DIM}")]
    return Div(head, Div(*cards, cls="flex-1 min-h-0 overflow-y-auto"),
               data_stage=col.stage.value, cls=f"min-w-0 min-h-0 flex flex-col border-l {LINE} first:border-l-0")


# --- widgets: each starts with its title; real data only (both journals read now) ----------------------------------
def board(ctx):
    """Board: the Quadro, the Upstream money band on top and one column per stage, each card with its Upstream money."""
    b: Board = read_board()
    return Div(_title("Quadro"), _band(b.totals),
               # gap-0: Pico's .grid has a column gap of its own
               Div(*[_column(c, b.at) for c in b.columns], style="grid-template-columns: repeat(4, minmax(0, 1fr))", cls="flex-1 min-h-0 grid gap-0"),
               Script(TICK_JS), Script(WATCH_JS % f"{BASE}/w/_/card.created/JournalStamp"),
               # a fresh snapshot every 10 s (a move by an agent, the clock started elsewhere) and at once when the money
               # bar starts, stops or enters on this page (devconsole-money); never while it is hidden
               hx_get=f"{BASE}/w/_/card.created/Board", hx_swap="outerHTML",
               hx_trigger="every 10s [this.offsetParent], devconsole-money from:document, devconsole-journal from:document, kanban-journal",
               data_board="1", data_stamp=_stamp(), cls="h-full min-h-[24rem] flex flex-col")


def journal_stamp(ctx):
    """Journal Stamp: when the Kanban journal last changed, so the Quadro knows to redraw (invisible)."""
    return Div(data_stamp=_stamp(), hidden=True)


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
    about = [Div(_title("Descrição"), *[P(ln, cls="font-sans text-sm text-neutral-800 dark:text-neutral-200") for ln in c.description.splitlines() if ln.strip()], cls="mb-3")] if c.description else []
    return Div(*about, _title("Histórico"), *rows)


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
    "card.created": [board, upstream_band, card_history, card_time, journal_stamp],
    "card.moved": [card_history],
    "card.prioritized": [board],
    "card.renamed": [card_history],
}
HOME = ("card.created", "Board")

