# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""The focus: one pointer to what the owner and the Bili are looking at now, and the console's home (`g h`).

The focus is a stack (set / back) kept in ONE place, an append-only journal:
`${DEV_CONSOLE_FOCUS_DIR:-~/.local/share/dev-console/focus}/events.jsonl`, one line per event
`{"id","event","at","actor","value"}` with `focus.set {text, target, card, by}` and `focus.back {by}`. This file is its
only writer (`focus.sh set|back|show`), and only the owner's conversation with the Bili moves it: `by` is `gabriel` or
`bili`, anything else is refused. Subagents and profiles never call `focus set`.

The default focus, with nothing set (or after `back` empties the stack), is the Kanban board (target `kanban`).
The home (`/`, and `g h` from any page) is the Kanban card in Doing with the current focus inside; with the Kanban as
the focus, or without a card in Doing, the home is the Kanban board. The screen never jumps by itself: the focus
changes behind, and `g h` takes the window there.

A target is one of: `kanban` (the board), a domain slug (`via`: its graph), a widget `<slug>/<event>/<Widget>`, or a
URL (a console path is embedded; any other URL shows the flight recorder's last shot of it).

Console side: `register(app, rt, json_response, ui)` adds `/home`, `/home/shot` and `GET /agent/focus`, and puts the
`g h` key on every full page (FastHTML's `app.hdrs`). Nothing here leaves the machine.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import re
import sys
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

SCRIPTS = Path(__file__).resolve().parent
BY = ("gabriel", "bili")  # only the owner's conversation with the Bili moves the focus
KANBAN = "kanban"  # the default focus: the Kanban board (the kanban domain's Quadro module)
DOING = ("Doing", "Downstream")  # the board's Doing: a stage named Doing when the Kanban has one, else Downstream
HISTORY = 5
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
WIDGET_RE = re.compile(r"^([a-z0-9][a-z0-9_-]*)/([A-Za-z0-9_.-]+)/([A-Za-z0-9_]+)$")
AT_RE = re.compile(r"^\d{8}T\d{6}\.\d{3}Z$")  # a flight recorder line's `at`, the name of its PNG


# --- value objects ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Focus:
    """What the owner and the Bili are looking at: a sentence, the target, the Kanban card it is for, who set it."""

    text: str
    target: str
    card: str | None = None
    by: str = ""
    at: str = ""

    @property
    def kind(self) -> str:
        return kind(self.target)


DEFAULT = Focus("o Quadro do Kanban", KANBAN)


def kind(target: str) -> str:
    """kanban | url | widget | slug; ValueError for anything else."""
    t = str(target or "").strip()
    if t == KANBAN:
        return "kanban"
    if t.startswith(("http://", "https://", "/")):
        return "url"
    if WIDGET_RE.match(t):
        return "widget"
    if SLUG_RE.match(t):
        return "slug"
    raise ValueError(f"target {t!r}: use kanban, a domain slug, <slug>/<event>/<Widget> or a URL")


def go_url(f: Focus, board: str) -> str:
    """Where a focus is when one goes there (a full page: navigation, never a focus change)."""
    k = f.kind
    if k == "kanban":
        return board
    if k == "slug":
        return f"/domain/{f.target}"
    if k == "widget":
        slug, ev, w = WIDGET_RE.match(f.target).groups()
        return f"/domain/{slug}?{urlencode({'ev': ev, 'w': w})}"
    return f.target


def embed_url(f: Focus, board: str) -> str:
    """The view inside the home, through the console's existing embed modes: a domain's graph alone (`embed=graph`), a
    widget's own route, a console page with `embed=1`. Any other URL is embedded as it is (or shown as a shot)."""
    k = f.kind
    if k == "kanban":
        return _with(board, embed="1")
    if k == "slug":
        return f"/domain/{f.target}?embed=graph"
    if k == "widget":
        slug, ev, w = WIDGET_RE.match(f.target).groups()
        return f"/domain/{slug}/w/_/{quote(ev)}/{quote(w)}"
    return _with(f.target, embed="1") if f.target.startswith("/") else f.target


def _with(url: str, **params) -> str:
    return url + ("&" if "?" in url else "?") + urlencode(params)


# --- the journal: pure folds ------------------------------------------------------------------------------------------
def _focus(e: dict) -> Focus:
    v = e.get("value") or {}
    return Focus(str(v.get("text", "")), str(v.get("target", KANBAN)), v.get("card") or None, str(v.get("by", e.get("actor", ""))),
                 str(e.get("at", "")))


def stack(events: list[dict]) -> list[Focus]:
    """The stack: each focus.set pushes, each focus.back pops (a back on an empty stack changes nothing)."""
    out: list[Focus] = []
    for e in events:
        if e.get("event") == "focus.set":
            try:
                kind((e.get("value") or {}).get("target", ""))
            except ValueError:
                continue
            out.append(_focus(e))
        elif e.get("event") == "focus.back" and out:
            out.pop()
    return out


def current(events: list[dict]) -> Focus:
    """The top of the stack, or the Kanban board when it is empty."""
    return (stack(events) or [DEFAULT])[-1]


def history(events: list[dict], n: int = HISTORY) -> list[Focus]:
    """The last n focuses set, newest first, without the current one and without repeats (same target and card)."""
    cur = current(events)
    seen, out = {(cur.target, cur.card)}, []
    for e in reversed(events):
        if e.get("event") != "focus.set":
            continue
        f = _focus(e)
        try:
            f.kind
        except ValueError:
            continue
        if (f.target, f.card) in seen:
            continue
        seen.add((f.target, f.card))
        out.append(f)
        if len(out) >= n:
            break
    return out


# --- the journal: the file --------------------------------------------------------------------------------------------
def focus_dir() -> Path:
    return Path(os.environ.get("DEV_CONSOLE_FOCUS_DIR", "~/.local/share/dev-console/focus")).expanduser()


def journal_path() -> Path:
    return focus_dir() / "events.jsonl"


def events() -> list[dict]:
    """Every line of the journal; a broken line is skipped, a missing file is empty."""
    try:
        raw = journal_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in raw:
        try:
            v = json.loads(line)
        except ValueError:
            continue
        if isinstance(v, dict):
            out.append(v)
    return out


@contextmanager
def _locked():
    journal_path().parent.mkdir(parents=True, exist_ok=True)
    with open(journal_path().with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _guard(by: str) -> str:
    if by not in BY:
        raise PermissionError(f"by={by!r}: only the owner's conversation with the Bili moves the focus (by: gabriel or bili); "
                              "subagents and profiles never call focus set")
    return by


def _append(event: str, value: dict, by: str) -> dict:
    line = {"id": uuid.uuid4().hex[:12], "event": event, "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "actor": by, "value": value}
    with _locked(), open(journal_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def set_focus(text: str, target: str, card: str | None, by: str, cards: list | None = None) -> dict:
    """focus.set: push a focus. `card` is resolved against the board (id, unique start of it, exact title) when the
    Kanban is readable, and stored as the card's id; an unknown or ambiguous card is refused."""
    _guard(by)
    text, target = str(text or "").strip(), str(target or "").strip()
    if not text:
        raise ValueError("a focus needs a sentence (text)")
    kind(target)
    if card:
        K = kanban()
        if K is not None:
            card = K.find(card, cards if cards is not None else K.cards_from(K.events())).id
    return _append("focus.set", {"text": text, "target": target, "card": card or None, "by": by}, by)


def back(by: str) -> dict:
    """focus.back: pop the focus; refused when the stack is already empty (the focus is the Kanban board)."""
    _guard(by)
    if not stack(events()):
        raise ValueError("the focus is already the Kanban board (the default): nothing to go back to")
    return _append("focus.back", {"by": by}, by)


# --- the Kanban card in Doing and its cost clock ----------------------------------------------------------------------
_KANBAN: list = []  # loaded once per process (a change to kanban.py restarts the console: its folder is watched)


def kanban():
    """The kanban skill's kanban.py beside this one (../../kanban/scripts), loaded by path; None when it is missing."""
    if _KANBAN:
        return _KANBAN[0]
    path = SCRIPTS.parent.parent / "kanban" / "scripts" / "kanban.py"
    mod = None
    if path.exists():
        try:
            spec = importlib.util.spec_from_file_location("focus_kanban", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["focus_kanban"] = mod  # dataclasses resolve their module by name
            spec.loader.exec_module(mod)
        except Exception:  # noqa: BLE001 - a broken neighbour must not take the home down: the board opens instead
            mod = None
    _KANBAN.append(mod)
    return mod


def doing_stage(stage_values: list[str]) -> str:
    """The stage that is the board's Doing: `Doing` when the Kanban has it, else Downstream (committed work)."""
    return next((s for s in DOING if s in stage_values), DOING[-1])


def doing_card(cards: list, ref: str | None, stage: str):
    """The card in Doing: the focus's card when it is there, else the one that entered Doing last; None without one."""
    doing = [c for c in cards if str(c.stage) == stage]
    if not doing:
        return None
    mine = [c for c in doing if ref and c.id == ref]
    return mine[0] if mine else max(enumerate(doing), key=lambda ic: (ic[1].since, ic[0]))[1]  # a tie: the later line


def doing_money(card, stage: str, entries: list, rates: dict, now: datetime, since: datetime | None = None) -> dict:
    """What the card's time in Doing cost: the time entries of its domain clipped to its Doing stays (and after
    `since`), each at its cost center's hour rate; `live_rate_hour` while the card is in Doing and the clock runs on its
    domain (the screen ticks from here, the money bar's way)."""
    spans = [(s.start, s.end or now) for s in card.stays if str(s.stage) == stage and (s.end or now) > s.start]
    seconds = brl = 0.0
    for t in entries:
        if t.domain != card.domain:
            continue
        rate = rates.get(t.center) or 0.0
        for a0, b0 in spans:
            a, b = max(t.start, a0, since or a0), min(t.end, b0)
            if b > a:
                sec = (b - a).total_seconds()
                seconds += sec
                brl += sec * rate / 3600
    live = next((t for t in entries if t.running and t.domain == card.domain), None) if str(card.stage) == stage else None
    return {"seconds": round(seconds, 1), "brl": round(brl, 2), "live_rate_hour": (rates.get(live.center) or 0.0) if live else 0.0}


# --- the snapshot: what the home, GET /agent/focus and focus.sh show draw ----------------------------------------------
def snapshot(board: str = "/domain/kanban?tab=Quadro", now: datetime | None = None, evs: list[dict] | None = None) -> dict:
    """{focus, card, history, cost_today, home, depth}: the current focus, the Kanban card in Doing (None without one),
    the last focuses, what the card's Doing cost today, and where `g h` goes (`/home`, or the board)."""
    now = now or datetime.now().astimezone()
    evs = events() if evs is None else evs
    f = current(evs)
    K = kanban()
    card = money = today = None
    if K is not None:
        try:
            cards = K.cards_from(K.events())
            stage = doing_stage([s.value for s in K.Stage])
            c = doing_card(cards, f.card, stage)
            if c is not None:
                entries, rates = K.cost_inputs(now)
                money = doing_money(c, stage, entries, rates, now)
                day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                t = doing_money(c, stage, entries, rates, now, since=day)
                today = {"seconds": t["seconds"], "brl": t["brl"]}
                card = {"id": c.id, "title": c.title, "domain": c.domain, "stage": str(c.stage), "since": c.since.isoformat(),
                        "seconds_in_stage": round((now - c.since).total_seconds()), "cost": money, "at": now.isoformat()}
        except Exception:  # noqa: BLE001 - a journal that does not parse must not take the home down
            card = today = None
    home = "/home" if (f.kind != "kanban" and card) else board

    def one(x: Focus) -> dict:
        return {**asdict(x), "kind": x.kind, "go": go_url(x, board)}

    return {"focus": {**one(f), "embed": embed_url(f, board), "default": not stack(evs)}, "card": card,
            "history": [one(x) for x in history(evs)], "cost_today": today, "home": home, "depth": len(stack(evs))}


# --- the console side --------------------------------------------------------------------------------------------------
# g h (g then h within 1 s, vim-style) on every page takes the window to the home: the top window, so it works from an
# embed too. Capture phase, so a canvas (tldraw) cannot swallow it; never while typing.
GH_JS = r"""
(() => {
  if (window.__devconsoleGH) return; window.__devconsoleGH = true;
  let g = 0;
  document.addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const el = document.activeElement;
    if (el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable)) return;
    if (e.key === 'g') { g = Date.now(); return; }
    if (e.key === 'h' && g && Date.now() - g <= 1000) {
      g = 0; e.preventDefault(); e.stopPropagation();
      (window.top || window).location.href = '/';
      return;
    }
    g = 0;
  }, true);
})();
"""

HOME_JS = r"""
// after the switcher's preamble ($, D, Q are its own)
const brl = v => 'R$ ' + v.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const ago = s => { const m = Math.floor(Math.max(s, 0) / 60); if (m < 1) return 'agora'; if (m < 60) return `há ${m} min`;
  const h = Math.floor(m / 60); if (h < 24) return `há ${h} h${m % 60 ? ` ${String(m % 60).padStart(2, '0')}` : ''}`;
  const d = Math.floor(h / 24); return `há ${d} dia${d > 1 ? 's' : ''}`; };
// the cost clock: the server's snapshot plus what the card gains per hour while the clock runs on its domain
function tick() {
  const now = Date.now();
  document.querySelectorAll('[data-brl]').forEach(el => {
    const at = +el.dataset.at, rate = +el.dataset.rate || 0;
    el.textContent = brl(+el.dataset.brl + rate * Math.max(0, now - at) / 3600000);
  });
  document.querySelectorAll('[data-since]').forEach(el => { el.textContent = ago((now - +el.dataset.since) / 1000); });
}
tick(); setInterval(tick, 1000);
// a history row goes to that focus (navigation, not a focus change): click, Enter or Space
document.querySelectorAll('[data-go]').forEach(r => {
  r.onclick = () => { location.href = r.dataset.go; };
  r.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); location.href = r.dataset.go; } };
});
"""


def _ms(iso: str) -> int:
    try:
        return int(datetime.fromisoformat(iso).timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def _shot_for(url: str, lines: list[dict]) -> dict | None:
    """The flight recorder's last line whose page is this URL (same path and query, any host), with a PNG."""
    want = urlsplit(url)
    for line in reversed(lines):
        got = urlsplit(str(line.get("url", "")))
        if (got.path, got.query) == (want.path, want.query) and AT_RE.match(str(line.get("at", ""))):
            return line
    return None


def register(app, rt, json_response, ui) -> None:
    """The home and the read route. `ui` brings the console's chrome: css, status_bar(name), switcher(), the switcher's
    script for a module href (switcher_js), board() (the board's URL, the default home) and recorder (console_recorder)."""
    from fasthtml.common import A, Div, Iframe, Img, Link, Script, Span, Style, Title
    from starlette.responses import FileResponse, RedirectResponse, Response

    app.hdrs.append(Script(GH_JS))  # every full page: g h

    @rt("/agent/focus")
    def agent_focus():
        """{focus, card, history[5], cost_today, home, depth}: read only (devc focus and focus.sh show read it)."""
        return json_response(snapshot(ui.board()))

    @rt("/home/shot")
    def home_shot(at: str = ""):
        """A flight recorder PNG by its `at` (only names of that shape, only from the recorder's shots folder)."""
        f = ui.recorder.recorder_dir() / "shots" / f"{at}.png"
        if not AT_RE.match(at) or not f.is_file():
            return Response("não encontrado", status_code=404)
        return FileResponse(f)

    @rt("/home")
    def home_page():
        """The Kanban card in Doing with the current focus inside; the board when the focus is the Kanban or no card is
        in Doing. Static: the focus changes behind, and only g h (or a reload) shows the new one."""
        s = snapshot(ui.board())
        if s["home"] != "/home":
            return RedirectResponse(s["home"], status_code=303)
        f, c = s["focus"], s["card"]
        dim, line = "text-neutral-400 dark:text-neutral-500", "border-neutral-200 dark:border-neutral-800"
        head = f"text-[11px] uppercase tracking-widest {dim}"
        cost = c["cost"]
        card = Div(
            Div(Div(c["title"], cls="font-sans text-xl font-semibold text-neutral-900 dark:text-neutral-100 truncate"),
                Div(Span(c["domain"]), Span(" · "), Span(f"em {c['stage']} "), Span("", data_since=str(_ms(c["since"]))),
                    cls=f"mt-1 {dim}"),
                cls="min-w-0"),
            Div(Div(Span("", data_brl=str(cost["brl"]), data_rate=str(cost["live_rate_hour"]), data_at=str(_ms(c["at"])),
                         cls="tabular-nums"),
                    cls="font-sans text-xl text-neutral-900 dark:text-neutral-100 text-right"),
                Div(f"o tempo em {c['stage']} até agora" + (" · correndo" if cost["live_rate_hour"] else ""),
                    cls=f"mt-1 text-right {dim}"),
                cls="shrink-0"),
            id="card", data_card=c["id"], cls=f"shrink-0 flex items-start justify-between gap-6 px-5 pt-4 pb-3 border-b {line}")
        if f["kind"] == "url" and not f["target"].startswith("/"):
            shot = _shot_for(f["target"], ui.recorder.read_lines())
            view = (Img(src=f"/home/shot?at={shot['at']}", alt=f["text"], cls="max-w-full")
                    if shot else Iframe(src=f["embed"], cls="w-full h-full border-0"))
        else:
            view = Iframe(src=f["embed"], id="focus-embed", cls="w-full h-full border-0")
        where = {"slug": "o grafo do domínio", "widget": "um widget", "url": "uma página", "kanban": "o quadro"}[f["kind"]]
        focus = Div(
            Div(Span("foco", cls=head), Span(f["text"], cls="text-neutral-800 dark:text-neutral-200 truncate"),
                A(f"{f['target']} · {where}", href=f["go"], cls=f"ml-auto shrink-0 {dim} hover:underline"),
                cls="shrink-0 flex items-center gap-3 px-5 h-9"),
            Div(view, id="focus-view", cls=f"flex-1 min-h-0 mx-5 mb-4 border {line} rounded overflow-auto"),
            cls="flex-1 min-w-0 min-h-0 flex flex-col")
        rows = [Div(Div(h["text"], cls="truncate text-neutral-700 dark:text-neutral-300"),
                    Div(Span(h["target"]), Span(" · "), Span("", data_since=str(_ms(h["at"]))), cls=f"truncate {dim}"),
                    data_go=h["go"], tabindex="0", aria_label=f"ir para {h['text']}",
                    cls="px-4 py-2 cursor-pointer hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 "
                        "dark:focus:bg-neutral-900 outline-none")
                for h in s["history"]]
        hist = Div(Div("antes", cls=f"{head} px-4 h-9 leading-9"),
                   *(rows or [Div("nenhum foco antes deste", cls=f"px-4 {dim}")]),
                   id="history", cls=f"w-64 shrink-0 overflow-y-auto border-l {line}")
        return Title(f"dev-console · {c['title']}"), Link(rel="icon", href="data:,"), Style(ui.css), Div(
            card,
            Div(focus, hist, id="work", cls="flex-1 min-h-0 flex"),
            ui.status_bar("Home"), ui.switcher(),
            Script(json.dumps(ui.data("/home"), ensure_ascii=False).replace("</", "<\\/"), type="application/json", id="data"),
            Script(ui.switcher_js("/home") + HOME_JS, type="module"),
            cls="h-screen flex flex-col font-mono text-xs bg-white dark:bg-neutral-950",
        )


# --- the CLI (focus.sh) ------------------------------------------------------------------------------------------------
def _print(s: dict) -> None:
    f, c = s["focus"], s["card"]
    print(f"foco: {f['text']}  [{f['target']}]" + ("  (o padrão)" if f["default"] else f"  por {f['by']}"))
    if c:
        print(f"card em Doing: {c['title']} · {c['domain']} · em {c['stage']} · R$ {c['cost']['brl']:.2f}"
              + (f" (hoje R$ {s['cost_today']['brl']:.2f})" if s["cost_today"] else ""))
    else:
        print("card em Doing: nenhum")
    print(f"home (g h): {s['home']}   pilha: {s['depth']}")
    for h in s["history"]:
        print(f"  antes: {h['text']}  [{h['target']}]  {h['at']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="focus.sh", description="the focus: set / back / show (only gabriel or bili move it)")
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("set", help="push a focus")
    ps.add_argument("text")
    ps.add_argument("--target", required=True, help="kanban | <domain slug> | <slug>/<event>/<Widget> | <url>")
    ps.add_argument("--card", help="the Kanban card it is for: id, a unique start of it, or its exact title")
    ps.add_argument("--by", required=True, help="gabriel or bili (the owner's conversation); anyone else is refused")
    pb = sub.add_parser("back", help="pop the focus (back to the previous one, the Kanban board at the bottom)")
    pb.add_argument("--by", required=True)
    pw = sub.add_parser("show", help="the current focus, the card in Doing, the last focuses")
    pw.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.cmd == "set":
            print(json.dumps(set_focus(a.text, a.target, a.card, a.by), ensure_ascii=False))
        elif a.cmd == "back":
            print(json.dumps(back(a.by), ensure_ascii=False))
        else:
            s = snapshot()
            print(json.dumps(s, ensure_ascii=False, indent=2)) if a.json else _print(s)
    except PermissionError as e:
        print(f"focus.sh: refused: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"focus.sh: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
