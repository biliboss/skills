# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Kanban: the owner's board. Each card is one piece of work tied to a dev-console domain, and it sits in one stage:
Upstream (discover and decide what to do), Downstream (deliver what was decided) or Feito (done). Drawn in the
dev-console as the Kanban domain, whose Quadro module is the console's home.

The names come from the Kanban Method (David J. Anderson, "Kanban: Successful Evolutionary Change for Your Technology
Business", 2010) and from Upstream Kanban (Patrick Steyaert, "Essential Upstream Kanban", 2018): the commitment point
splits the board in two, upstream the options still being discovered, downstream the work committed to.

Money: a card's Upstream time is priced from the Costs journal (skill cost-track, read only, never written here): the
time entries of the card's domain, clipped to the stays in which the card was in Upstream, at the hour rate of the
entry's cost center (costs.rate_hour: an investment center is priced at the goal). The band sums the cards' Upstream
time for today, this week (from Monday) and this month (from the 1st).

The journal is a global append-only JSONL, ~/.local/share/kanban/events.jsonl (override KANBAN_DIR), one line per event
{"id","event","at","actor","card_id","value"}. This file is its only writer, through kanban.sh:

    kanban.sh create "<title>" --domain <slug> [--stage Todo|Upstream|Downstream|Feito] [--force] [--actor <who>]
    kanban.sh move <card> <stage> [--force] [--actor <who>]   # exit 4 when the stage is at its limit (Upstream 1)
    kanban.sh pull "<title>" [--domain D] [--repo DIR] [--context T|--context-file F] [--center C] [--no-switch]
                    [--swap] [--json]               # exit 5 {"full": title} when Upstream has no room
    kanban.sh list [--stage <stage>] [--json]
    kanban.sh show <card> [--json]
    kanban.sh money [--json]
    kanban.sh wip [--repo owner/name] [--json]      # open PRs of the repo; exit 3 at or over the WIP limit (wip.limit, 3)
    kanban.sh sweep [--hours 48] [--repos a/b,c/d] [--apply] [--json]
                                                    # open PRs and branches older than N hours; --apply closes what is
                                                    # already in main and records item.aged / decision.requested

The screen only draws what the pure functions below return (board, card_money, upstream_totals). Stdlib only.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

EVENTS = {
    "card": {
        # Um card entrou no quadro: um trabalho com título, ligado a um domínio do dev-console, numa etapa (em geral
        # Upstream, quando ainda se descobre o que fazer).
        "create": "created",
        # O card mudou de etapa: de Upstream (descobrir e decidir) para Downstream (entregar o que foi decidido), para
        # Feito, ou de volta. Só o tempo em Upstream entra no investimento do card.
        "move": "moved",
        # O dono ordenou a fila de uma etapa: o card ficou na posição dada (0 = o topo, o card em foco agora). Quem nunca
        # foi ordenado vem depois dos ordenados, por chegada; mudar de etapa zera a posição.
        "prioritize": "prioritized",
        # O card ganhou outro título (a mesma coisa, melhor nomeada); o histórico e o dinheiro seguem o card.
        "rename": "renamed",
        # O card ganhou a descrição: o pedido de alto nível (por quê, para quem, resultado, limites, pronto quando). A
        # última vale; a primeira linha ("Por quê: ...") aparece sob o título no quadro.
        "describe": "described",
    },
    "item": {
        # Uma PR aberta ou uma branch passou de N horas (48 por padrão) sem entrar na main: o que foi começado e não
        # terminou. Não é um card: é o varredor diário que enxerga (value: repo, kind pr|branch, ref, age_h).
        "age": "aged",
    },
    "decision": {
        # Só o dono decide: um merge que publica (repo cujo main faz deploy), uma branch com trabalho fora da main.
        # O varredor nunca decide por ele (value: text, repo, ref, reason).
        "request": "requested",
    },
}

# The edges: a card is created, then moves as often as the work needs (back to Upstream too).
TRANSITIONS = {
    "card.created": ["card.moved", "card.prioritized", "card.renamed", "card.described"],
    "card.moved": ["card.moved", "card.prioritized", "card.renamed", "card.described"],
    "card.prioritized": ["card.moved", "card.prioritized", "card.renamed", "card.described"],
    "card.renamed": ["card.moved", "card.prioritized", "card.renamed", "card.described"],
}


# --- the value objects: the screen and the CLI draw only these ------------------------------------------------------
class Stage(str, Enum):
    """Where a card is on the board: discovering, delivering, or done."""

    __str__ = str.__str__  # str() and f-strings give the value, as StrEnum did (it is 3.11+; the console allows 3.10)

    TODO = "Todo"  # the backlog: waiting, not worked now (its time is not Upstream money)
    UPSTREAM = "Upstream"  # discover and decide what to do (before the commitment point)
    DOWNSTREAM = "Downstream"  # deliver what was decided
    DONE = "Feito"  # done


@dataclass(frozen=True)
class NewCard:
    """What card.created carries: the title, the dev-console domain it belongs to, and the stage it starts in."""

    title: str
    domain: str  # a dev-console domain slug: that domain's time in Costs is the card's time
    stage: Stage


@dataclass(frozen=True)
class Move:
    """What card.moved carries: the stage the card entered and the one it left."""

    stage: Stage
    previous: Stage


@dataclass(frozen=True)
class Prioritize:
    """What card.prioritized carries: the place in the stage's queue (0 = the top, the card in focus) and the stage."""

    position: int
    stage: Stage


@dataclass(frozen=True)
class Rename:
    """What card.renamed carries: the new title."""

    title: str


@dataclass(frozen=True)
class Describe:
    """What card.described carries: the card's description (last wins)."""

    text: str


@dataclass(frozen=True)
class Stay:
    """One stay of a card in a stage: from when it entered to when it left (None while it is still there)."""

    stage: Stage
    start: datetime
    end: datetime | None = None


@dataclass(frozen=True)
class Card:
    """A card of the board, folded from its events: what it is, its domain, where it is now and since when."""

    id: str
    title: str
    domain: str
    stage: Stage  # the current stage (the last stay's)
    since: datetime  # when it entered the current stage
    created_at: datetime
    stays: tuple[Stay, ...]  # every stay, oldest first; the last one is still open
    rank: int | None = None  # its place in the owner's order of the stage (0 = top); None = never ranked there
    description: str = ""  # the last card.described text: the high-level request (por quê ... pronto quando)

    @property
    def why(self) -> str:
        """The description's first line, what the board shows under the title."""
        return next((ln.strip() for ln in self.description.splitlines() if ln.strip()), "")


@dataclass(frozen=True)
class TimeEntry:
    """A stretch of the cost clock in one domain, read from the Costs journal: a stopped entry, or the one running."""

    id: str  # the time_entry.stopped event's id, or "running"
    domain: str
    center: str  # the cost center the stretch was billed to: the domain's
    start: datetime
    end: datetime
    running: bool = False  # the stretch running now: its end is the moment of the reading


@dataclass(frozen=True)
class Slice:
    """The part of a time entry that fell while a card was in Upstream (a partial overlap is clipped), priced."""

    entry: str  # the time entry's id
    start: datetime
    end: datetime
    seconds: float
    rate_hour: float  # R$ per hour of the entry's cost center today (0 when the center or the worth is unknown)
    brl: float  # seconds x rate_hour, in R$, rounded to cents
    running: bool = False


@dataclass(frozen=True)
class Money:
    """Time and what it is worth."""

    seconds: float
    brl: float


@dataclass(frozen=True)
class CardMoney:
    """What a card cost while it was in Upstream: its slices of time, their total, and the R$ per hour it gains now (only
    while the card is in Upstream and the clock runs on its domain; 0 otherwise)."""

    card: Card
    slices: tuple[Slice, ...]
    total: Money
    live_rate_hour: float = 0.0


@dataclass(frozen=True)
class UpstreamTotals:
    """The money band: the Upstream time of every card today, this week (from Monday) and this month (from the 1st),
    and the R$ per hour the three gain now while the clock runs on the domain of a card in Upstream."""

    today: Money
    week: Money
    month: Money
    live_rate_hour: float  # 0 when nothing ticks
    live_domain: str  # the domain the clock runs on while it ticks; "" otherwise
    at: datetime  # the moment the numbers are true: the screen ticks from here


@dataclass(frozen=True)
class Column:
    """One column of the board: a stage and its cards, in the order they arrived there."""

    stage: Stage
    cards: tuple[CardMoney, ...]
    limit: int | None = None  # the WIP limit of the stage (stage_limits); None = unlimited


@dataclass(frozen=True)
class Board:
    """The Quadro as the screen draws it: the money band on top, then one column per stage."""

    totals: UpstreamTotals
    columns: tuple[Column, ...]
    at: datetime


# Which value object each event carries (the dev-console's Code shows it with the event).
VALUES = {"card.created": "NewCard", "card.moved": "Move", "card.prioritized": "Prioritize", "card.renamed": "Rename", "card.described": "Describe"}


# --- pure functions: journal events in, value objects out (no file, no clock) ----------------------------------------
# The console's own rule (dev-console's _settle): a running stretch nobody pinged for this long ended at its last ping.
STALE_SECONDS = 45


def parse_at(iso: str) -> datetime:
    """A journal time; one written without an offset is local time."""
    t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return t if t.tzinfo else t.astimezone()


def stage_of(text: Any) -> Stage:
    """The stage a person or an agent named, in any case (upstream, FEITO); ValueError otherwise."""
    for s in Stage:
        if str(text).strip().casefold() == s.value.casefold():
            return s
    raise ValueError(f"unknown stage {text!r}; one of {', '.join(s.value for s in Stage)}")


def card_from(events: list[dict]) -> Card | None:
    """One card's events, oldest first, folded into its Card; None before its card.created. A move to the stage it is
    already in changes nothing; a line a hand edit broke is skipped."""
    head: dict | None = None
    stays: list[Stay] = []
    for e in events:
        v = e.get("value") or {}
        kind = e.get("event")
        if kind not in ("card.created", "card.moved", "card.renamed", "card.described"):
            continue
        try:
            at = parse_at(e["at"])
            stage = (stage_of(v.get("stage") or (Stage.UPSTREAM if kind == "card.created" else ""))
                     if kind not in ("card.renamed", "card.described") else Stage.UPSTREAM)
        except (KeyError, ValueError):
            continue
        if kind == "card.described":
            if head is not None and str(v.get("text") or "").strip():
                head["description"] = str(v["text"]).strip()
        elif kind == "card.renamed":
            if head is not None and str(v.get("title") or "").strip():
                head["title"] = str(v["title"]).strip()
        elif kind == "card.created" and head is None:
            head = {"id": e.get("card_id", ""), "title": v.get("title", ""), "domain": v.get("domain", ""), "at": at}
            stays = [Stay(stage, at)]
        elif kind == "card.moved" and head is not None and stage is not stays[-1].stage:
            stays[-1] = Stay(stays[-1].stage, stays[-1].start, at)
            stays.append(Stay(stage, at))
    if head is None:
        return None
    return Card(head["id"], head["title"], head["domain"], stays[-1].stage, stays[-1].start, head["at"], tuple(stays),
                None, head.get("description", ""))


def cards_from(events: list[dict]) -> list[Card]:
    """Every card of the Kanban journal, in the order they were created."""
    groups: dict[str, list[dict]] = {}
    for e in events:
        if e.get("card_id"):
            groups.setdefault(e["card_id"], []).append(e)
    cards = {c.id: c for g in groups.values() if (c := card_from(g))}
    ranks = ranks_from(events)
    return [replace(c, rank=ranks.get(c.id)) for c in cards.values()]


def ranks_from(events: list[dict]) -> dict[str, int]:
    """The owner's order, replayed. Each stage has its queue as the board shows it: the ranked cards first, then the
    rest by arrival. card.prioritized takes the card out of that queue and puts it at its position (0 = top), so `rank N`
    lands at N on screen; the queue it leaves is kept as the explicit order. A move to another stage drops the card from
    the old order (the rank is cleared) and it arrives last in the new one. A prioritize naming a stage the card is no
    longer in is ignored. Returns the index of each ranked card."""
    where: dict[str, str] = {}
    arrival: dict[str, list[str]] = {}  # every card of the stage, by arrival
    ranked: dict[str, list[str]] = {}
    for e in events:
        cid, v, kind = e.get("card_id"), e.get("value") or {}, e.get("event")
        if not cid:
            continue
        try:
            stage = stage_of(v.get("stage") or (Stage.UPSTREAM if kind == "card.created" else "")).value
        except ValueError:
            continue
        if kind == "card.created" and cid not in where:
            where[cid] = stage
            arrival.setdefault(stage, []).append(cid)
        elif kind == "card.moved" and cid in where and where[cid] != stage:
            old = where[cid]
            arrival[old].remove(cid)
            if cid in ranked.get(old, []):
                ranked[old].remove(cid)
            where[cid] = stage
            arrival.setdefault(stage, []).append(cid)
        elif kind == "card.prioritized" and where.get(cid) == stage:
            try:
                pos = max(0, int(v.get("position")))
            except (TypeError, ValueError):
                continue
            first = ranked.setdefault(stage, [])
            queue = first + [c for c in arrival[stage] if c not in first]
            queue.remove(cid)
            queue.insert(min(pos, len(queue)), cid)
            ranked[stage] = queue
    return {cid: i for queue in ranked.values() for i, cid in enumerate(queue)}


def time_entries(cost_events: list[dict], running: dict | None, now: datetime) -> list[TimeEntry]:
    """The clock's stretches, from the Costs journal. A stopped entry runs from its time_entry.started (same center and
    domain) for its seconds: its own `at` is when it was written, later than its end after an idle trim or a quiet page.
    The running stretch (the costs folder's running.json) runs until now; one nobody pinged for STALE_SECONDS ended at
    its last ping, where the console will close it."""
    out: list[TimeEntry] = []
    started: dict[tuple[str, str], datetime] = {}
    for e in cost_events:
        v = e.get("value") or {}
        key = (e.get("cost_center") or "", v.get("domain") or "")
        try:
            at = parse_at(e["at"])
        except (KeyError, ValueError):
            continue
        if e.get("event") == "time_entry.started":
            started[key] = at
        elif e.get("event") == "time_entry.stopped":
            seconds = float(v.get("seconds") or 0)
            start = started.pop(key, None) or at - timedelta(seconds=seconds)
            if seconds > 0 and key[1]:
                out.append(TimeEntry(e.get("id", ""), key[1], key[0], start, start + timedelta(seconds=seconds)))
    if running and running.get("domain") and running.get("started_at"):
        try:
            start = parse_at(running["started_at"])
            seen = parse_at(running.get("last_seen") or running["started_at"])
        except ValueError:
            return out
        live = running.get("driver") == "tmux" or (now - seen).total_seconds() <= STALE_SECONDS
        end = now if live else max(seen, start)
        if end > start:
            out.append(TimeEntry("running", running["domain"], running.get("center") or "", start, end, running=live))
    return out


def upstream_spans(card: Card, now: datetime) -> list[tuple[datetime, datetime]]:
    """When the card was in Upstream: each Upstream stay, the open one until now."""
    return [(s.start, s.end or now) for s in card.stays if s.stage is Stage.UPSTREAM and (s.end or now) > s.start]


def _merged(spans: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _cut(entry: TimeEntry, spans: list[tuple[datetime, datetime]], rates: dict[str, float],
         since: datetime | None = None) -> list[Slice]:
    """The parts of one time entry inside the spans (and after `since`), each priced at its center's hour rate."""
    rate = rates.get(entry.center) or 0.0
    out = []
    for s0, s1 in spans:
        a, b = max(entry.start, s0, since or s0), min(entry.end, s1)
        if b > a:
            sec = (b - a).total_seconds()
            out.append(Slice(entry.id, a, b, sec, rate, round(sec * rate / 3600, 2), entry.running))
    return out


def _sum(slices: list[Slice] | tuple[Slice, ...]) -> Money:
    return Money(sum(s.seconds for s in slices), round(sum(s.brl for s in slices), 2))


def card_money(card: Card, entries: list[TimeEntry], rates: dict[str, float], now: datetime) -> CardMoney:
    """A card's Upstream money: the time entries of its domain clipped to its Upstream stays (time before, between and
    after them does not count), each priced at its cost center's hour rate; live while the card is in Upstream and the
    clock runs on its domain."""
    spans = upstream_spans(card, now)
    slices = tuple(sorted((s for t in entries if t.domain == card.domain for s in _cut(t, spans, rates)),
                          key=lambda s: s.start))
    live = next((t for t in entries if t.running and t.domain == card.domain), None) if card.stage is Stage.UPSTREAM else None
    return CardMoney(card, slices, _sum(slices), (rates.get(live.center) or 0.0) if live else 0.0)


def periods(now: datetime) -> tuple[datetime, datetime, datetime]:
    """Where today, this week (Monday) and this month (the 1st) start: midnight on `now`'s own clock."""
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return day, day - timedelta(days=day.weekday()), day.replace(day=1)


def upstream_totals(cards: list[Card], entries: list[TimeEntry], rates: dict[str, float], now: datetime) -> UpstreamTotals:
    """The band: every card's Upstream time today, this week and this month. A second of the clock counts once: two
    cards of one domain in Upstream at the same time share its time (each card shows it whole, the band counts it
    once). Live while the clock runs on the domain of a card that is in Upstream now."""
    spans: dict[str, list[tuple[datetime, datetime]]] = {}
    for c in cards:
        spans.setdefault(c.domain, []).extend(upstream_spans(c, now))
    merged = {d: _merged(s) for d, s in spans.items()}

    def since(t0: datetime) -> Money:
        return _sum([s for t in entries for s in _cut(t, merged.get(t.domain, []), rates, t0)])

    day, week, month = periods(now)
    live = next((t for t in entries if t.running
                 and any(c.stage is Stage.UPSTREAM and c.domain == t.domain for c in cards)), None)
    return UpstreamTotals(since(day), since(week), since(month), (rates.get(live.center) or 0.0) if live else 0.0,
                          live.domain if live else "", now)


def board(cards: list[Card], entries: list[TimeEntry], rates: dict[str, float], now: datetime) -> Board:
    """The Quadro: the band, then the three columns, each card with its money: the owner's order first (the top is the card in focus), then the rest by arrival."""
    money = [card_money(c, entries, rates, now) for c in cards]
    limits = stage_limits()
    columns = tuple(Column(st, tuple(sorted((m for m in money if m.card.stage is st), key=lambda m: (m.card.rank is None, m.card.rank or 0, m.card.since))), limits.get(st))
                    for st in Stage)
    return Board(upstream_totals(cards, entries, rates, now), columns, now)


# --- the words and numbers a person reads (the money bar's formats) ------------------------------------------------
def brl(v: float) -> str:
    """R$ 1.234,56"""
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def hm(seconds: float) -> str:
    """0h50: whole minutes, as the money bar shows them."""
    m = int(max(seconds, 0) // 60)
    return f"{m // 60}h{m % 60:02d}"


def stage_age(seconds: float) -> str:
    """How long a card has been in its stage, for a person, counting up: há 12 s, há 5 min 07 s, há 3 h 05 min, há 2
    dias (each followed by na etapa). The Quadro's browser code (`age` in dev_console_project.py) writes the same words."""
    s = int(max(seconds, 0))
    if s < 60:
        return f"há {s} s na etapa"
    m = s // 60
    if m < 60:
        return f"há {m} min {s % 60:02d} s na etapa"
    h = m // 60
    if h < 24:
        return f"há {h} h {m % 60:02d} min na etapa"
    d = h // 24
    return f"há {d} dia{'s' if d > 1 else ''} na etapa"


def short(seconds: float) -> str:
    """45m, 3h12m, 2d4h: a duration in a terminal column."""
    m = int(max(seconds, 0) // 60)
    if m < 60:
        return f"{m}m"
    if m < 24 * 60:
        return f"{m // 60}h{m % 60:02d}m"
    return f"{m // 1440}d{m % 1440 // 60}h"


# --- the journal: the one writer, and the reads -----------------------------------------------------------------------
KNOWN_EVENTS = [f"{cat}.{ev}" for cat, cmds in EVENTS.items() for ev in dict.fromkeys(cmds.values())]
CARDLESS = {"item.aged": ("repo", "kind", "ref", "age_h"), "decision.requested": ("text", "repo", "ref", "reason")}
DOMAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def kanban_dir() -> Path:
    """The folder of the journal; read on every call so KANBAN_DIR may change."""
    return Path(os.environ.get("KANBAN_DIR", "~/.local/share/kanban")).expanduser()


def journal_path() -> Path:
    return kanban_dir() / "events.jsonl"


def _parse(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue  # a torn or hand-broken line never hides the rest
    return out


def events() -> list[dict]:
    """Every event of the Kanban journal, oldest first."""
    path = journal_path()
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return _parse(f.read())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def _locked():
    """The journal open for append under an exclusive lock, with the events already in it (read under the same lock, so
    a move's `previous` cannot race another writer)."""
    path = journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            yield f, _parse(f.read())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _now() -> datetime:
    return datetime.now().astimezone()


class StageFull(ValueError):
    """A stage is at its WIP limit and the card was not forced in (exit 4)."""


STAGE_FULL_EXIT = 4


def _check_limit(stage: Stage, cards: list[Card], card_id: str | None, force: bool) -> None:
    """Refuse to put one more card in a stage at its limit, naming who is there; `force` records the exception instead."""
    limit = stage_limits().get(stage)
    if limit is None or force:
        return
    there = [c.title for c in cards if c.stage is stage and c.id != card_id]
    if len(there) >= limit:
        raise StageFull(f"{stage.value} está cheio ({len(there)}/{limit}): {', '.join(there)}. "
                        f"Mova-o antes, ou use --force para registrar a exceção.")


def emit(event: str, value: dict, card_id: str | None = None, actor: str = "agent", at: datetime | None = None) -> dict:
    """Append one event (id and `at` generated) and return it: the only writer of the Kanban journal. card.created takes
    {title, domain, stage} (stage defaults to Todo; the card id is generated when not given); card.moved takes
    {stage} for an existing card that is in another stage, and records `previous` itself."""
    if event not in KNOWN_EVENTS:
        raise ValueError(f"unknown event {event!r}; known: {', '.join(KNOWN_EVENTS)}")
    if not isinstance(value, dict):
        raise ValueError("the value must be a JSON object")
    if event in CARDLESS:  # the sweep's events belong to a repo item, not to a card
        missing = [k for k in CARDLESS[event] if not value.get(k) and value.get(k) != 0]
        if missing:
            raise ValueError(f"{event} needs {', '.join(missing)}")
        if event == "item.aged" and value["kind"] not in ("pr", "branch"):
            raise ValueError("item.aged kind is pr or branch")
        with _locked() as (f, _past):
            record = {"id": uuid.uuid4().hex[:12], "event": event, "at": (at or _now()).isoformat(timespec="seconds"),
                      "actor": actor, "card_id": None, "value": value}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return record
    with _locked() as (f, past):
        cards = {c.id: c for c in cards_from(past)}
        if event == "card.created":
            new = NewCard(str(value.get("title") or "").strip(), str(value.get("domain") or "").strip(),
                          stage_of(value.get("stage") or Stage.TODO))
            if not new.title:
                raise ValueError("a card needs a title")
            if not DOMAIN_RE.match(new.domain):
                raise ValueError(f"a card needs the dev-console domain it belongs to (a slug), got {new.domain!r}")
            card_id = card_id or uuid.uuid4().hex[:8]
            if card_id in cards:
                raise ValueError(f"card {card_id} already exists")
            _check_limit(new.stage, list(cards.values()), None, bool(value.get("force")))
            val: dict = {"title": new.title, "domain": new.domain, "stage": new.stage.value}
            if value.get("force"):
                val["forced"] = True
        else:
            card = cards.get(card_id or "")
            if card is None:
                raise ValueError(f"no card {card_id!r}")
            if event == "card.renamed":
                title = str(value.get("title") or "").strip()
                if not title:
                    raise ValueError("a card needs a title")
                if title == card.title:
                    raise ValueError(f"card {card.id} is already titled {title!r}")
                val = {"title": title}
                record = {"id": uuid.uuid4().hex[:12], "event": event, "at": (at or _now()).isoformat(timespec="seconds"),
                          "actor": actor, "card_id": card_id, "value": val}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
                return record
            if event == "card.described":
                text = str(value.get("text") or "").strip()
                if not text:
                    raise ValueError("a description needs text")
                if text == card.description:
                    raise ValueError(f"card {card.id} already has this description")
                record = {"id": uuid.uuid4().hex[:12], "event": event, "at": (at or _now()).isoformat(timespec="seconds"),
                          "actor": actor, "card_id": card_id, "value": {"text": text}}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
                return record
            if event == "card.prioritized":
                try:
                    pos = int(value.get("position"))
                except (TypeError, ValueError):
                    raise ValueError("position is a whole number, 0 is the top") from None
                if pos < 0:
                    raise ValueError("position is a whole number, 0 is the top")
                pr = Prioritize(pos, card.stage)
                record = {"id": uuid.uuid4().hex[:12], "event": event, "at": (at or _now()).isoformat(timespec="seconds"),
                          "actor": actor, "card_id": card_id, "value": {"position": pr.position, "stage": pr.stage.value}}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
                return record
            mv = Move(stage_of(value.get("stage", "")), card.stage)
            if mv.stage is mv.previous:
                raise ValueError(f"card {card.id} ({card.title}) is already in {card.stage.value}")
            _check_limit(mv.stage, list(cards.values()), card.id, bool(value.get("force")))
            val = {"stage": mv.stage.value, "previous": mv.previous.value}
            if value.get("force"):
                val["forced"] = True
        record = {"id": uuid.uuid4().hex[:12], "event": event, "at": (at or _now()).isoformat(timespec="seconds"),
                  "actor": actor, "card_id": card_id, "value": val}
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return record


def create(title: str, domain: str, stage: Stage | str = Stage.TODO, actor: str = "agent",
           at: datetime | None = None, force: bool = False) -> dict:
    """card.created: a new card in a stage (Todo by default); `force` goes past the stage's limit and records it."""
    return emit("card.created", {"title": title, "domain": domain, "stage": str(stage), **({"force": True} if force else {})},
                actor=actor, at=at)


def move(card_id: str, stage: Stage | str, actor: str = "agent", at: datetime | None = None, force: bool = False) -> dict:
    """card.moved: a card to another stage; `force` goes past the stage's limit and records it."""
    return emit("card.moved", {"stage": str(stage), **({"force": True} if force else {})}, card_id, actor, at)


def prioritize(card_id: str, position: int, actor: str = "agent", at: datetime | None = None) -> dict:
    """card.prioritized: the card at `position` in its stage's queue (0 = the top, the card in focus)."""
    return emit("card.prioritized", {"position": position}, card_id, actor, at)


def rename(card_id: str, title: str, actor: str = "agent", at: datetime | None = None) -> dict:
    """card.renamed: the card under a new title."""
    return emit("card.renamed", {"title": title}, card_id, actor, at)


def describe(card_id: str, text: str, actor: str = "agent", at: datetime | None = None) -> dict:
    """card.described: the card's description, the high-level request; the last one wins."""
    return emit("card.described", {"text": text}, card_id, actor, at)


def find(ref: str, cards: list[Card]) -> Card:
    """The card a person or an agent named: its id, a unique start of its id (3 characters or more), or its exact
    title in any case. ValueError when none or several match."""
    ref = str(ref).strip()
    tests = (lambda c: c.id == ref, lambda c: len(ref) >= 3 and c.id.startswith(ref),
             lambda c: c.title.casefold() == ref.casefold())
    for test in tests:
        hits = [c for c in cards if test(c)]
        if len(hits) == 1:
            return hits[0]
        if hits:
            raise ValueError(f"{ref!r} names {len(hits)} cards: " + ", ".join(f"{c.id} ({c.title})" for c in hits))
    raise ValueError(f"no card {ref!r}")


def _project(events: list[dict]) -> dict:
    """A card as the journal leaves it, the dict the dev-console reads (Card is the same thing as a value object)."""
    c = card_from(events)
    if c is None:
        return {}
    state = {
        "id": c.id,
        "title": c.title,
        # the dev-console domain the card belongs to
        "domain": c.domain,
        # Upstream, Downstream or Feito
        "stage": c.stage.value,
        # when it entered its stage
        "since": c.since.isoformat(timespec="seconds"),
        "created_at": c.created_at.isoformat(timespec="seconds"),
        "updated_at": events[-1]["at"],
        # the last card.described text, "" when none
        "description": c.description,
    }
    return state


class KanbanJournal:
    """Read-only view of the Kanban journal for the dev-console contract."""

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        evs = events()
        if "id" in query:
            mine = [e for e in evs if e.get("card_id") == query["id"]]
            return mine if query.get("history") else _project(mine)
        if "event" in query:
            return [e for e in evs if e.get("event") == query["event"]]
        if query.get("history"):
            return evs
        groups: dict[str, list[dict]] = {}
        for e in evs:
            if e.get("card_id"):
                groups.setdefault(e["card_id"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]


# --- reading the Costs journal (cost-track's costs.py, read only) ----------------------------------------------------
@cache
def _costs():
    """cost-track's costs.py beside this skill (../../cost-track/scripts/costs.py), loaded by path; None when it is
    missing (the board then shows its cards without money)."""
    path = Path(__file__).resolve().parent.parent.parent / "cost-track" / "scripts" / "costs.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("kanban_costs", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001 - a broken neighbour must not break the board
        return None


def cost_inputs(now: datetime) -> tuple[list[TimeEntry], dict[str, float]]:
    """The clock's time entries and the hour rate of each cost center, read from the Costs journal now."""
    costs = _costs()
    if costs is None:
        return [], {}
    rates = {cid: costs.rate_hour(cid) or 0.0 for cid in costs.centers()}
    return time_entries(costs.events(), costs.running(), now), rates


def read_board(now: datetime | None = None) -> Board:
    """The Quadro now: both journals read, then the pure functions."""
    now = now or _now()
    entries, rates = cost_inputs(now)
    return board(cards_from(events()), entries, rates, now)


def read_card(card_id: str, now: datetime | None = None) -> CardMoney | None:
    """One card's money now (None when there is no such card)."""
    now = now or _now()
    card = next((c for c in cards_from(events()) if c.id == card_id), None)
    if card is None:
        return None
    entries, rates = cost_inputs(now)
    return card_money(card, entries, rates, now)


# --- the CLI (kanban.sh) ---------------------------------------------------------------------------------------------
def _jsonable(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat(timespec="seconds")
    raise TypeError(f"{type(o).__name__} is not JSON")


def as_json(obj: Any) -> str:
    return json.dumps(asdict(obj) if is_dataclass(obj) else obj, ensure_ascii=False, indent=2, default=_jsonable)


def _when(t: datetime) -> str:
    return t.astimezone().strftime("%Y-%m-%d %H:%M")


def _print_list(b: Board, stage: Stage | None) -> None:
    cols = [col for col in b.columns if stage is None or col.stage is stage]
    print("  ".join(f"{col.stage.value} {len(col.cards)}" + (f"/{col.limit}" if col.limit else "") for col in cols))
    rows = [m for col in cols for m in col.cards]
    print(f"{'ID':<10}{'STAGE':<12}{'IN STAGE':<10}{'UPSTREAM R$':>14}{'TIME':>8}  {'DOMAIN':<16}TITLE")
    for m in rows:
        c = m.card
        print(f"{c.id:<10}{c.stage.value:<12}{short((b.at - c.since).total_seconds()):<10}{brl(m.total.brl):>14}"
              f"{hm(m.total.seconds):>8}  {c.domain:<16}{c.title}")
    if not rows:
        print("(no cards)")


def _print_card(m: CardMoney, now: datetime) -> None:
    c = m.card
    print(f"{c.title}  ({c.id})")
    print(f"  domain    {c.domain}")
    if c.description:
        print("  intent")
        for ln in c.description.splitlines():
            print(f"    {ln}" if ln.strip() else "")
    print(f"  stage     {c.stage.value} since {c.since.isoformat(timespec='seconds')} ({short((now - c.since).total_seconds())})")
    print("  stays")
    for s in c.stays:
        print(f"    {s.stage.value:<12}{_when(s.start)} -> {_when(s.end) if s.end else 'now'}")
    live = f"  (live +{brl(m.live_rate_hour)}/h)" if m.live_rate_hour else ""
    print(f"  upstream  {brl(m.total.brl)}  {hm(m.total.seconds)}{live}")
    for s in m.slices:
        end = "now" if s.running else s.end.astimezone().strftime("%H:%M")
        print(f"    {_when(s.start)} -> {end}  {hm(s.seconds)}  {brl(s.brl)}  at {brl(s.rate_hour)}/h")
    if not m.slices:
        print("    (no Upstream time yet)")


def _print_money(b: Board) -> None:
    t = b.totals
    print(f"Upstream time of the cards, at {t.at.isoformat(timespec='seconds')}")
    for label, mo in (("Hoje", t.today), ("Semana", t.week), ("Mês", t.month)):
        print(f"  {label:<8}{brl(mo.brl):>14}  {hm(mo.seconds)}")
    print(f"  live    +{brl(t.live_rate_hour)}/h, the clock runs on {t.live_domain}" if t.live_rate_hour
          else "  live    no (the clock is not running on the domain of a card in Upstream)")
    print("per card (all its Upstream time)")
    for col in b.columns:
        for m in col.cards:
            print(f"  {m.card.id:<10}{m.card.stage.value:<12}{brl(m.total.brl):>14}  {hm(m.total.seconds):>6}  {m.card.title}")


# --- the WIP limit and the aging sweep: what was started and not finished (gh, never the journal's cards) -----------------
DEFAULT_WIP_LIMIT = 3
WIP_EXIT = 3  # `wip` exits with it at or over the limit
# repos whose main deploys: nothing is closed, deleted or merged there by the sweep, only asked to the owner
DEPLOY_OWNERS = ("viacorretor",)
DEPLOY_REPOS = ("the-viacorretor",)


def config() -> dict:
    """~/.config/kanban/config.json (override KANBAN_CONFIG), when it exists and parses: {"wip": {"limit": 3}}."""
    path = Path(os.environ.get("KANBAN_CONFIG", "~/.config/kanban/config.json")).expanduser()
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (ValueError, OSError):
        return {}


DEFAULT_STAGE_LIMITS = {"Upstream": 1}


def stage_limits() -> dict[Stage, int]:
    """The WIP limit per stage: Upstream 1 by default; config `stage_limits` {"Stage": n} overrides it (0 = unlimited)."""
    cfg = config().get("stage_limits")
    merged: dict[Stage, Any] = {}
    for name, n in [*DEFAULT_STAGE_LIMITS.items(), *(cfg.items() if isinstance(cfg, dict) else [])]:
        try:
            merged[stage_of(name)] = int(n)  # any case; the config comes after the defaults
        except (TypeError, ValueError):
            continue
    return {st: n for st, n in merged.items() if n > 0}


def wip_limit(repo: str | None = None) -> int:
    """wip.limit (default 3); wip.repos {"owner/name": n} overrides it for one repo."""
    wip = config().get("wip") or {}
    try:
        return int((wip.get("repos") or {}).get(repo or "", wip.get("limit", DEFAULT_WIP_LIMIT)))
    except (TypeError, ValueError):
        return DEFAULT_WIP_LIMIT


def _gh(*args: str) -> str:
    """gh (override KANBAN_GH); the output, or ValueError with what it said."""
    done = subprocess.run([os.environ.get("KANBAN_GH", "gh"), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise ValueError(f"gh {' '.join(args[:3])} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def _gh_json(*args: str) -> Any:
    try:
        return json.loads(_gh(*args) or "null")
    except json.JSONDecodeError as err:
        raise ValueError(f"gh {' '.join(args[:3])}: not JSON ({err})") from err


def open_prs(repo: str) -> list[dict]:
    return _gh_json("pr", "list", "-R", repo, "--state", "open", "--limit", "200", "--json",
                    "number,title,headRefName,createdAt,url") or []


def wip(repo: str | None = None) -> dict:
    """The open PRs of a repo against its limit. Without a repo: the one of the current directory."""
    if not repo:
        repo = str((_gh_json("repo", "view", "--json", "nameWithOwner") or {}).get("nameWithOwner") or "")
        if not repo:
            raise ValueError("no repo: pass --repo owner/name")
    prs = open_prs(repo)
    limit = wip_limit(repo)
    return {"repo": repo, "open": len(prs), "limit": limit, "over": len(prs) >= limit,
            "prs": [{"number": x["number"], "title": x["title"], "branch": x["headRefName"], "url": x.get("url", "")}
                    for x in prs]}


def deploys(repo: str) -> bool:
    owner, _, name = repo.lower().partition("/")
    return owner in DEPLOY_OWNERS or name in DEPLOY_REPOS


def _age_h(iso: str, now: datetime) -> float:
    return round((now - parse_at(iso.replace("Z", "+00:00"))).total_seconds() / 3600, 1)


def _in_main(repo: str, default: str, branch: str) -> tuple[bool, int]:
    """(is the branch's content already in main, commits ahead). Squash merges leave the commits ahead, so when it is
    ahead every changed file is compared with main's: identical blobs everywhere means the content landed."""
    cmp = _gh_json("api", f"repos/{repo}/compare/{default}...{branch}") or {}
    ahead = int(cmp.get("ahead_by") or 0)
    if ahead == 0:
        return True, 0
    files = cmp.get("files") or []
    if not files or len(files) >= 300:
        return False, ahead  # unknown or too big to prove: not in main
    for f in files:
        name = f["filename"]
        same = False
        try:
            on_branch = _gh_json("api", f"repos/{repo}/contents/{name}?ref={branch}") or {}
        except ValueError:
            on_branch = {}
        try:
            on_main = _gh_json("api", f"repos/{repo}/contents/{name}?ref={default}") or {}
        except ValueError:
            on_main = {}
        same = on_branch.get("sha") == on_main.get("sha")  # both missing (a deleted file) counts as equal
        if not same:
            return False, ahead
    return True, ahead


def _recent(evs: list[dict], event: str, repo: str, ref: str, now: datetime) -> bool:
    """The same item was already reported in the last 24 h: the daily sweep says it once."""
    for e in reversed(evs):
        v = e.get("value") or {}
        if e.get("event") == event and v.get("repo") == repo and v.get("ref") == ref:
            try:
                return (now - parse_at(e["at"])).total_seconds() < 24 * 3600
            except (KeyError, ValueError):
                return False
    return False


def sweep(repos: list[str], hours: float = 48, apply: bool = False, actor: str = "kanban-sweep",
          now: datetime | None = None) -> dict:
    """Open PRs and branches older than `hours`. Read only unless `apply`: then a PR whose content is already in main is
    closed, a remote branch already in main is deleted, and the rest is recorded (item.aged; decision.requested for a
    merge that publishes and for a branch with work outside main). Unmerged work is never deleted and nothing is ever
    merged; a repo whose main deploys only gets decision.requested."""
    now = now or _now()
    past = events() if apply else []
    items: list[dict] = []
    errors: list[str] = []
    for repo in repos:
        try:
            default = str((_gh_json("api", f"repos/{repo}") or {}).get("default_branch") or "main")
            prs = open_prs(repo)
            pr_heads = {x["headRefName"] for x in prs}
            guarded = deploys(repo)
            for x in prs:
                age = _age_h(x["createdAt"], now)
                if age < hours:
                    continue
                landed, _ = _in_main(repo, default, x["headRefName"])
                items.append({"repo": repo, "kind": "pr", "ref": f"#{x['number']} {x['headRefName']}", "number": x["number"],
                              "branch": x["headRefName"], "age_h": age, "in_main": landed, "deploys": guarded,
                              "title": x["title"]})
            branches = _gh_json("api", f"repos/{repo}/branches?per_page=100") or []
            for b in branches:
                name = b["name"]
                if name == default or name in pr_heads:
                    continue
                commit = _gh_json("api", f"repos/{repo}/commits/{name}") or {}
                age = _age_h(commit["commit"]["committer"]["date"], now)
                if age < hours:
                    continue
                landed, ahead = _in_main(repo, default, name)
                items.append({"repo": repo, "kind": "branch", "ref": name, "age_h": age, "in_main": landed, "ahead": ahead,
                              "deploys": guarded})
        except (ValueError, KeyError) as err:
            errors.append(f"{repo}: {err}")
    for it in items:
        if it["deploys"]:
            it["action"] = "decision"
            it["reason"] = "the repo's main deploys: a merge publishes; only the owner decides"
        elif it["in_main"]:
            it["action"] = "close" if it["kind"] == "pr" else "delete"
        elif it["kind"] == "branch":
            it["action"] = "decision"
            it["reason"] = "a branch with work that is not in main"
        else:
            it["action"] = "aged"
    if apply:
        for it in items:
            repo, ref = it["repo"], it["ref"]
            try:
                if it["action"] == "close":
                    _gh("pr", "close", str(it["number"]), "-R", repo, "--comment",
                        "Closed by the kanban sweep: this content is already in main.")
                    it["done"] = "closed"
                elif it["action"] == "delete":
                    _gh("api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/{ref}")
                    it["done"] = "deleted"
                else:
                    if not _recent(past, "item.aged", repo, ref, now):
                        emit("item.aged", {"repo": repo, "kind": it["kind"], "ref": ref, "age_h": it["age_h"]}, actor=actor)
                        it["recorded"] = ["item.aged"]
                    if it["action"] == "decision" and not _recent(past, "decision.requested", repo, ref, now):
                        emit("decision.requested", {"text": f"{repo} {ref}: {it.get('reason')}", "repo": repo, "ref": ref,
                                                    "reason": it["reason"]}, actor=actor)
                        it.setdefault("recorded", []).append("decision.requested")
            except ValueError as err:
                errors.append(f"{repo} {ref}: {err}")
    # a PR closed above turns its branch into a branch in main: the next sweep deletes it (one thing at a time)
    return {"hours": hours, "applied": apply, "items": items, "errors": errors}


def _print_wip(w: dict) -> None:
    flag = "AT OR OVER THE LIMIT" if w["over"] else "ok"
    print(f"{w['repo']}: {w['open']} open PR(s), limit {w['limit']}: {flag}")
    for x in w["prs"]:
        print(f"  #{x['number']:<5}{x['branch']:<40}{x['title']}")


def _print_sweep(r: dict) -> None:
    by: dict[str, int] = {}
    for it in r["items"]:
        by[it["action"]] = by.get(it["action"], 0) + 1
        extra = f"  [{it.get('done') or ','.join(it.get('recorded', []))}]" if r["applied"] else ""
        print(f"{it['repo']:<28}{it['kind']:<7}{it['age_h']:>7.1f} h  {it['action']:<9}{it['ref']}{extra}")
    for e in r["errors"]:
        print(f"error: {e}", file=sys.stderr)
    total = ", ".join(f"{n} {a}" for a, n in sorted(by.items())) or "nothing"
    print(f"sweep >{r['hours']:g} h ({'applied' if r['applied'] else 'dry run'}): {len(r['items'])} item(s): {total}")


# --- pull: one gesture to start a piece of work (Kanban Method: work is pulled, not pushed) ---------------------------
PULL_FULL_EXIT = 5  # Upstream is full: the caller asks the owner what happens to the current card
OPEN_STAGES = (Stage.TODO, Stage.UPSTREAM, Stage.DOWNSTREAM)


def slug(text: str) -> str:
    """The name of a piece of work: the same slug as cost-track's tmux_focus.py (the tmux session, the Hermes session)."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _sibling(skill: str, *parts: str) -> Path:
    return Path(__file__).resolve().parent.parent.parent / skill / "scripts" / Path(*parts)


def default_context(title: str, domain: str) -> str:
    return (f"Sessão do cartão \"{title}\" (Kanban, Upstream; domínio {domain}). O Gabriel vai trabalhar nisso agora. "
            "Leia o README e o .wiki do repositório, responda em até 6 linhas o que já existe sobre isso e termine "
            "perguntando o objetivo. Upstream é descoberta: não escreva código ainda.")


def pull(title: str, domain: str | None, repo: str, context: str | None, center: str | None, switch: bool,
         swap: bool, actor: str) -> dict:
    """The card (reuse the open one with this slug, else create in Upstream), the cost center binding, the workspace
    (hermes.sh workspace: Hermes session + tmux session named slug) and the owner's tmux client. StageFull is raised
    as `PullFull` before anything is written when Upstream has no room and --swap was not given."""
    name = slug(title)
    if not name:
        raise ValueError("the title has no letters or digits to make a slug from")
    cards = cards_from(events())
    mine = sorted((c for c in cards if c.stage in OPEN_STAGES and slug(c.title) == name), key=lambda c: c.since, reverse=True)
    card = mine[0] if mine else None
    card_state = "reused"
    limit = stage_limits().get(Stage.UPSTREAM)
    if card is None or card.stage is not Stage.UPSTREAM:
        there = [c for c in cards if c.stage is Stage.UPSTREAM]
        extra = len(there) - limit + 1 if limit else 0
        if extra > 0:
            if not swap:
                raise PullFull(there[0].title)
            for c in there[:extra]:
                move(c.id, Stage.TODO, actor)
        if card is None:
            card_state = "created"
            ev_ = create(title, domain or name, Stage.UPSTREAM, actor)
            card = card_from([e for e in events() if e.get("card_id") == ev_["card_id"]])
            if card is None:
                raise ValueError("the new card is not in the journal")
        else:
            card_state = f"moved from {card.stage.value}"
            move(card.id, Stage.UPSTREAM, actor)
            card = replace(card, stage=Stage.UPSTREAM)
    domain = card.domain
    bound = None
    if center:
        costs = _costs()
        if costs is None:
            raise ValueError("cost-track is not beside this skill: cannot bind the cost center")
        bound = costs.bind(center, domain, actor) is not None
    ws = ["bash", os.environ.get("HERMES_SH") or str(_sibling("hermes", "hermes.sh")), "workspace", name, "--repo", repo,
          "--context", context or default_context(title, domain)]
    r = subprocess.run(ws, capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError(f"hermes.sh workspace failed (exit {r.returncode}): {(r.stderr or r.stdout).strip()[-400:]}")
    workspace = json.loads(r.stdout.strip().splitlines()[-1])
    _name_tab(name, card.id, card.title)
    return {"slug": name, "plan": _start_plan(name, domain, repo), "card": {"id": card.id, "title": card.title, "domain": domain, "stage": "Upstream",
                                   "state": card_state},
            "center": {"id": center, "domain": domain, "bound_now": bound} if center else None,
            "workspace": workspace, "switched": _switch_client(name) if switch else None}


def _name_tab(session: str, card_id: str, title: str) -> bool:
    """Name the card's agent window (tmux tab) with its title. The window is the one tagged `@card=<id>`, else the first
    one (which gets tagged); automatic-rename goes off so the shell does not take the name back. The session keeps its
    slug name (cost-track and the Quadro look it up). Best effort: no tmux or no session is False, never an error."""
    tmux = os.environ.get("TMUX_BIN", "tmux")
    try:
        r = subprocess.run([tmux, "list-windows", "-t", f"={session}", "-F", "#{window_index} #{@card}"],
                           capture_output=True, text=True)
        rows = [ln.split(" ", 1) + [""] for ln in r.stdout.splitlines() if ln.strip()]
        if r.returncode != 0 or not rows:
            return False
        rows.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0)
        idx = next((x[0] for x in rows if x[1].strip() == card_id), rows[0][0])
        target = f"={session}:{idx}"
        steps = (["rename-window", "-t", target, title], ["set-option", "-w", "-t", target, "automatic-rename", "off"],
                 ["set-option", "-w", "-t", target, "@card", card_id])
        return all(subprocess.run([tmux, *a], capture_output=True).returncode == 0 for a in steps)
    except OSError:
        return False


def _start_plan(name: str, domain: str, repo: str) -> dict | None:
    """Upstream is planning: open the card's plan (skill domain-plan, `plan.sh start`). Never fails the pull: a missing
    skill is None, a failed start is {"error"}."""
    sh = Path(os.environ.get("PLAN_SH") or _sibling("domain-plan", "plan.sh"))
    if not sh.exists():
        return None
    r = subprocess.run(["bash", str(sh), "start", name, "--repo", repo, "--domain", domain], capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip().splitlines()
    return {"started": r.returncode == 0, "note": out[-1] if out else ""}


class PullFull(Exception):
    """Upstream is at its limit; carries the title of the card in the way."""


def _switch_client(name: str) -> str | None:
    """Point the owner's most recently active tmux client at the session; its tty, or None when no client is attached."""
    tmux = os.environ.get("TMUX_BIN", "tmux")
    r = subprocess.run([tmux, "list-clients", "-F", "#{client_activity} #{client_tty}"], capture_output=True, text=True)
    rows = sorted((ln.split(None, 1) for ln in r.stdout.splitlines() if len(ln.split(None, 1)) == 2), reverse=True)
    if r.returncode != 0 or not rows:
        return None
    tty = rows[0][1]
    ok = subprocess.run([tmux, "switch-client", "-c", tty, "-t", f"={name}"], capture_output=True).returncode == 0
    return tty if ok else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kanban.sh", description="The Kanban journal's only writer, and the board read from it.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="a new card (card.created)")
    c.add_argument("title")
    c.add_argument("--domain", required=True, help="the dev-console domain slug the card belongs to")
    c.add_argument("--stage", default=Stage.TODO.value, help="Todo (default), Upstream, Downstream or Feito")
    c.add_argument("--force", action="store_true", help="go past the stage's WIP limit; recorded as forced")
    c.add_argument("--actor", default="agent")
    m = sub.add_parser("move", help="a card to another stage (card.moved)")
    m.add_argument("card", help="its id, a unique start of its id, or its exact title")
    m.add_argument("stage", help="Todo, Upstream, Downstream or Feito")
    m.add_argument("--force", action="store_true", help="go past the stage's WIP limit; recorded as forced")
    m.add_argument("--actor", default="agent")
    tp = sub.add_parser("top", help="a card to the top of its stage: the card in focus (card.prioritized, position 0)")
    tp.add_argument("card", help="its id, a unique start of its id, or its exact title")
    tp.add_argument("--actor", default="agent")
    rk = sub.add_parser("rank", help="a card to a position of its stage's queue (card.prioritized; 0 = top)")
    rk.add_argument("card")
    rk.add_argument("position", type=int, help="0 is the top")
    rk.add_argument("--actor", default="agent")
    rn = sub.add_parser("rename", help="a card under another title (card.renamed)")
    rn.add_argument("card")
    rn.add_argument("title")
    rn.add_argument("--actor", default="agent")
    ds = sub.add_parser("describe", help="a card's description, the 5-field request (card.described; last wins)")
    ds.add_argument("card")
    g = ds.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="a file with the text")
    g.add_argument("--text")
    ds.add_argument("--actor", default="agent")
    ls = sub.add_parser("list", help="the cards, per stage, with their Upstream money")
    ls.add_argument("--stage")
    ls.add_argument("--json", action="store_true")
    sh = sub.add_parser("show", help="one card: its stays and its Upstream time")
    sh.add_argument("card")
    sh.add_argument("--json", action="store_true")
    mo = sub.add_parser("money", help="the band (Hoje, Semana, Mês) and each card's Upstream money")
    mo.add_argument("--json", action="store_true")
    wp = sub.add_parser("wip", help="open PRs of a repo against the WIP limit; exit 3 at or over it")
    wp.add_argument("--repo", help="owner/name (default: the current directory's repo)")
    wp.add_argument("--json", action="store_true")
    pl = sub.add_parser("pull", help="start a piece of work: its card in Upstream, its Hermes + tmux sessions, the client there")
    pl.add_argument("title")
    pl.add_argument("--domain", help="the card's domain (default: the slug of the title; a reused card keeps its own)")
    pl.add_argument("--repo", default=os.getcwd(), help="the project's directory (default: here)")
    g = pl.add_mutually_exclusive_group()
    g.add_argument("--context", help="the first message of the Hermes session")
    g.add_argument("--context-file", help="the same, read from a file")
    pl.add_argument("--center", help="bind the card's domain to this cost center (cost_center.updated, once)")
    pl.add_argument("--no-switch", action="store_true", help="do not move the owner's tmux client")
    pl.add_argument("--swap", action="store_true", help="when Upstream is full, send its current card back to Todo")
    pl.add_argument("--json", action="store_true")
    pl.add_argument("--actor", default="agent")
    sw = sub.add_parser("sweep", help="open PRs and branches older than N hours; --apply closes what is already in main")
    sw.add_argument("--hours", type=float, default=48)
    sw.add_argument("--repos", required=True, help="owner/name,owner/name")
    sw.add_argument("--apply", action="store_true")
    sw.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "create":
            print(json.dumps(create(a.title, a.domain, a.stage, a.actor, force=a.force), ensure_ascii=False))
        elif a.cmd == "move":
            card = find(a.card, cards_from(events()))
            print(json.dumps(move(card.id, a.stage, a.actor, force=a.force), ensure_ascii=False))
        elif a.cmd == "pull":
            ctx = Path(a.context_file).expanduser().read_text() if a.context_file else a.context
            repo = str(Path(a.repo).expanduser())
            r = pull(a.title, a.domain, repo, ctx, a.center, not a.no_switch, a.swap, a.actor)
            if a.json:
                print(json.dumps(r, ensure_ascii=False))
            else:
                w, c = r["workspace"], r["card"]
                print(f"{c['title']} [{c['stage']}, {c['domain']}] card {c['state']}; Hermes {w['session']}, tmux {w['tmux']} "
                      f"({r['slug']}); " + (f"client {r['switched']} -> {r['slug']}" if r["switched"] else "client not switched"))
        elif a.cmd in ("top", "rank"):
            card = find(a.card, cards_from(events()))
            print(json.dumps(prioritize(card.id, 0 if a.cmd == "top" else a.position, a.actor), ensure_ascii=False))
        elif a.cmd == "rename":
            card = find(a.card, cards_from(events()))
            out = rename(card.id, a.title, a.actor)
            _name_tab(slug(card.title), card.id, a.title.strip())  # the tab follows the title; the session keeps its slug
            print(json.dumps(out, ensure_ascii=False))
        elif a.cmd == "describe":
            card = find(a.card, cards_from(events()))
            try:
                text = Path(a.file).read_text(encoding="utf-8") if a.file else a.text
            except OSError as err:
                raise ValueError(f"cannot read {a.file}: {err.strerror}") from err
            print(json.dumps(describe(card.id, text, a.actor), ensure_ascii=False))
        elif a.cmd == "list":
            b = read_board()
            stage = stage_of(a.stage) if a.stage else None
            if a.json:
                print(as_json([asdict(m) for col in b.columns if stage is None or col.stage is stage for m in col.cards]))
            else:
                _print_list(b, stage)
        elif a.cmd == "wip":
            w = wip(a.repo)
            print(json.dumps(w, ensure_ascii=False)) if a.json else _print_wip(w)
            return WIP_EXIT if w["over"] else 0
        elif a.cmd == "sweep":
            r = sweep([x.strip() for x in a.repos.split(",") if x.strip()], a.hours, a.apply)
            print(json.dumps(r, ensure_ascii=False)) if a.json else _print_sweep(r)
            return 1 if r["errors"] else 0
        elif a.cmd == "show":
            now = _now()
            cm = read_card(find(a.card, cards_from(events())).id, now)
            print(as_json(cm)) if a.json else _print_card(cm, now)
        else:
            b = read_board()
            print(as_json(b)) if a.json else _print_money(b)
    except PullFull as err:
        print(json.dumps({"full": str(err)}, ensure_ascii=False))
        print(f"kanban: Upstream está cheio ({err}); use --swap para o atual voltar ao Todo", file=sys.stderr)
        return PULL_FULL_EXIT
    except StageFull as err:
        print(f"kanban: {err}", file=sys.stderr)
        return STAGE_FULL_EXIT
    except ValueError as err:
        print(f"kanban: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
