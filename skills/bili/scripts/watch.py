# /// script
# requires-python = ">=3.11"
# dependencies = ["nats-py>=2.9"]
# ///
"""watch: one readable line per NATS event worth a human's attention, for a terminal or Claude Code's Monitor.

Pick what to watch by name; with no names it watches `asks` and `errors`:

    uv run --script scripts/watch.py                 # asks + errors
    uv run --script scripts/watch.py asks panes llm  # several
    uv run --script scripts/watch.py --list          # what each name covers

The subjects behind each name come from a JSON file when CASA_BILI_WATCH_SUBJECTS_FILE is set
(`{"asks": ["x.pane.*.ask"], "errors": ["x.log.>"]}`: names not in the file keep the built-in subjects).
The file only changes WHERE to listen; what each name prints stays the formatter's.

Only new events (no replay), stdout flushed per line, the same line is not repeated within 60 s.
Field names are read in English and in the older Portuguese ones while both exist on the stream.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from collections.abc import Callable

import nats

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
REPEAT_WINDOW_S = 60
# Panes never reported by `panes` (comma list; default: the owner's own pane, CASA_DONO_PANE).
IGNORE_PANES = set(filter(None, os.environ.get("WATCH_IGNORE_PANES", os.environ.get("CASA_DONO_PANE", "")).split(",")))


def pick(d: dict, *keys: str, default=""):
    """The first key present (English first, the older Portuguese name after)."""
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


# Same shapes as prime_bili.secrets_filter: a secret that slipped past the publisher never reaches the screen.
SECRETS = re.compile(r"(sk-[A-Za-z0-9_-]{6,}|gh[pousr]_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}|xox[baprs]-[A-Za-z0-9-]{8,}"
                     r"|Bearer\s+[A-Za-z0-9._-]{12,}|[A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{40,})")


def one_line(text, limit: int = 200) -> str:
    return SECRETS.sub("«redacted»", " ".join(str(text).split()))[:limit]


def fmt_ask(subject: str, ev: dict) -> str | None:
    pane = pick(ev, "pane", default=subject.split(".")[2])
    return f"ASK {pane} {pick(ev, 'kind', default='ask')}: {one_line(pick(ev, 'question', 'pergunta'))}"


def fmt_error(subject: str, ev: dict) -> str | None:
    if subject.startswith("mesa.log.hermes."):
        if pick(ev, "level", "nivel") == "WARNING":
            return None  # a command that exited non-zero is routine for an agent; only ERROR needs a human
        profile = subject.split(".")[3]
        return f"ERROR hermes/{profile} {pick(ev, 'tool')}: {one_line(pick(ev, 'type', 'tipo', 'message'))}"
    if pick(ev, "ok", default=True) is False:  # mesa.llm.* and mesa.jev.* failures
        return f"ERROR {subject}: {one_line(pick(ev, 'error', 'erro'))}"
    return None


def fmt_pane(subject: str, ev: dict) -> str | None:
    before, after = pick(ev, "before", "antes", default={}), pick(ev, "after", "depois", default={})
    old, new = pick(before, "state", "estado"), pick(after, "state", "estado")
    if pick(after, "name", "nome") in IGNORE_PANES:
        return None  # the watcher's own pane (the human's session) is not news to the human
    stopped = old == "working" and new in ("done", "idle")
    if not after or old == new or not (stopped or new == "blocked"):
        return None  # only when work stops or an agent blocks; done <-> idle is the same "stopped"
    return f"PANE {pick(after, 'id')} {pick(after, 'name', 'nome')}: {old} -> {new}"


def fmt_llm(subject: str, ev: dict) -> str | None:
    ms = pick(ev, "ms", default=0)
    if pick(ev, "ok", default=True) is not False and ms < 60_000:
        return None  # only failures and calls slower than a minute
    return f"LLM {pick(ev, 'model', 'modelo')} {ms / 1000:.0f}s ok={pick(ev, 'ok')}: {one_line(pick(ev, 'error', 'erro'))}"


def fmt_route(subject: str, ev: dict) -> str | None:
    return (f"ROUTE {pick(ev, 'route', 'rota')} -> {pick(ev, 'target', 'alvo', default='-')}: "
            f"{one_line(pick(ev, 'request', 'pedido'), 90)} ({one_line(pick(ev, 'reason', 'porque'), 80)})")


def fmt_cycle(subject: str, ev: dict) -> str | None:
    lead = pick(ev, "lead_time_ms", "duration_ms", default=0)
    return f"DONE {pick(ev, 'agent')} {lead / 1000:.0f}s: {one_line(pick(ev, 'text', 'request'), 120)}"


# name -> (subjects, formatter, what it covers)
WATCHES: dict[str, tuple[list[str], Callable[[str, dict], str | None], str]] = {
    "asks": (["mesa.pane.*.ask"], fmt_ask, "a pane waiting for a human: Hermes Clarify/approval, herdr blocked"),
    "errors": (["mesa.log.hermes.*.erro", "mesa.llm.>", "mesa.jev.>"], fmt_error,
               "Hermes errors, failed Claude endpoint calls, failed Jev calls"),
    "panes": (["mesa.pane.*"], fmt_pane, "an agent that stopped, finished or got blocked"),
    "llm": (["mesa.llm.>"], fmt_llm, "Claude endpoint calls that failed or took over a minute"),
    "routes": (["mesa.rota.*", "mesa.route.*"], fmt_route, "every routing decision"),
    "cycle": (["mesa.agent.request.answered"], fmt_cycle, "every answered request, with its lead time"),
}


def load_subjects(path: str | None) -> None:
    """Override the subjects of the named watches from a JSON file {name: [subject, ...]}."""
    if not path:
        return
    try:
        with open(os.path.expanduser(path)) as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"watch: cannot read {path}: {e}")
    if not isinstance(cfg, dict):
        sys.exit(f"watch: {path} must be a JSON object {{name: [subjects]}}")
    for name, subjects in cfg.items():
        if name not in WATCHES:
            sys.exit(f"watch: {path}: unknown watch {name!r}; known: {', '.join(WATCHES)}")
        if not isinstance(subjects, list) or not subjects or not all(isinstance(x, str) and x for x in subjects):
            sys.exit(f"watch: {path}: {name!r} must be a non-empty list of subjects")
        _, fmt, about = WATCHES[name]
        WATCHES[name] = (subjects, fmt, about)


async def main(names: list[str]) -> None:
    nc = await nats.connect(NATS_URL, max_reconnect_attempts=-1)
    seen: dict[str, float] = {}

    def handler(fmt):
        async def on_msg(msg):
            try:
                ev = json.loads(msg.data)
            except ValueError:
                return
            line = fmt(msg.subject, ev) if isinstance(ev, dict) else None
            now = time.time()
            if line and now - seen.get(line, 0) > REPEAT_WINDOW_S:
                seen[line] = now
                print(line, flush=True)
        return on_msg

    for name in names:
        subjects, fmt, _ = WATCHES[name]
        for subject in subjects:
            await nc.subscribe(subject, cb=handler(fmt))
    print(f"watching: {', '.join(names)}", file=sys.stderr, flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    args = sys.argv[1:]
    load_subjects(os.environ.get("CASA_BILI_WATCH_SUBJECTS_FILE"))
    if "--list" in args or "-h" in args or "--help" in args:
        for name, (subjects, _, about) in WATCHES.items():
            print(f"{name:8} {about}  [{', '.join(subjects)}]")
        sys.exit(0)
    unknown = [a for a in args if a not in WATCHES]
    if unknown:
        sys.exit(f"watch: unknown {', '.join(unknown)}; try --list")
    asyncio.run(main(args or ["asks", "errors"]))
