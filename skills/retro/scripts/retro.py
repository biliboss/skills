# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Retro: at the end of a session, the owner's corrections become rules in the skills. Design stage, drawn in the
dev-console as the Retro domain.

The practice is the after-action review (US Army: what was expected, what happened, why, what changes) and the agile
retrospective; the mechanics follow Hermes Agent's background review (grounded lessons, patch the skill in play, one
lesson one rule, a do-not-capture list) and claude-reflect (the owner picks, dedupe before writing). Sources:
references/prior-art.md.

Prototype: the journal is a global append-only JSONL, ~/.local/share/retro/events.jsonl (override RETRO_DIR), easy to
edit by hand.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

JOURNAL = Path(os.environ.get("RETRO_DIR", "~/.local/share/retro")).expanduser() / "events.jsonl"

EVENTS = {
    "retro": {
        # O dono chamou /retro: a sessão (ou as últimas N, lidas do JSONL quando a conversa foi compactada) vai ser
        # revisada atrás de correções, retrabalho, erros contornados e o que deu certo.
        "start": "started",
    },
    "lesson": {
        # Uma lição achada, com a frase do dono como prova: a skill onde mora, a regra numa frase com o porquê, o tipo
        # (falta na skill, ou instrução ambígua) e se é nova ou reforça uma regra que já existe.
        "propose": "proposed",
        # O dono marcou a lição no multi-select: ela entra na skill.
        "accept": "accepted",
        # O dono recusou, com o motivo (repetida, errada, específica demais); a mesma recusa duas vezes some das
        # próximas retros.
        "reject": "rejected",
        # A regra entrou na skill: o PR foi juntado, com o trecho que mudou.
        "apply": "applied",
        # A mesma correção voltou numa sessão que carregou a skill: a regra existe e não está funcionando (mal escrita
        # ou mal posicionada), e a próxima retro reforça em vez de copiar.
        "recur": "recurred",
    },
}

# The edges, in the order the story happens: the owner starts a retro, lessons are proposed, he picks, the accepted
# ones land in a skill, and a lesson that comes back is proposed again as a reinforcement.
TRANSITIONS = {
    "retro.started": ["lesson.proposed"],
    "lesson.proposed": ["lesson.accepted", "lesson.rejected"],
    "lesson.accepted": ["lesson.applied"],
    "lesson.applied": ["lesson.recurred"],
    "lesson.recurred": ["lesson.proposed"],
}


def _project(events: list[dict]) -> dict:
    """A lesson as the journal leaves it: where it lives, its rule and how it went."""
    if not events:
        return {}
    state = {"id": events[-1]["lesson"], "skill": "", "rule": "", "status": "", "recurred": 0, "updated_at": events[-1]["at"]}
    for e in events:
        v = e.get("value", {})
        kind = e["event"].split(".")[1]
        if kind == "proposed":
            state.update(skill=v.get("skill", ""), rule=v.get("rule", ""))
        if kind == "recurred":
            state["recurred"] += 1
        state["status"] = kind
    return state


class RetroJournal:
    """Read-only view of the Retro journal for the dev-console contract."""

    def _events(self) -> list[dict]:
        if not JOURNAL.exists():
            return []
        return [json.loads(line) for line in JOURNAL.read_text().splitlines() if line.strip()]

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        events = self._events()
        if "id" in query:
            matches = [e for e in events if e.get("lesson") == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for e in events:
            if e.get("lesson"):
                groups.setdefault(e["lesson"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]


# ---- CLI: the only writer of the journal (uv run --script retro.py emit|lessons|rejected-rules|scan) ----

import argparse  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime  # noqa: E402


def journal_path() -> Path:
    """The journal, read from RETRO_DIR on every call."""
    return Path(os.environ.get("RETRO_DIR", "~/.local/share/retro")).expanduser() / "events.jsonl"


def _all_events() -> list[dict]:
    p = journal_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def emit(event: str, value: dict, lesson: str | None = None, actor: str = "agent") -> dict:
    valid = {f"{d}.{k}" for d, kinds in EVENTS.items() for k in kinds.values()}
    if event not in valid:
        raise ValueError(f"unknown event {event!r}; one of {sorted(valid)}")
    if not isinstance(value, dict) or not value.get("text"):
        raise ValueError("value must be an object with a non-empty `text`")
    if event.startswith("lesson.") and not lesson:
        raise ValueError(f"{event} requires --lesson <id>")
    row: dict[str, Any] = {"id": uuid.uuid4().hex[:12], "event": event}
    if lesson:
        row["lesson"] = lesson
    row.update(at=datetime.now().astimezone().isoformat(timespec="seconds"), actor=actor, value=value)
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def lessons(status: str | None = None) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for e in _all_events():
        if e.get("lesson"):
            groups.setdefault(e["lesson"], []).append(e)
    out = [s for g in groups.values() if (s := _project(g))]
    return [s for s in out if not status or s["status"] == status]


def _norm(rule: str) -> str:
    return re.sub(r"\W+", " ", rule.lower()).strip()


def rejected_rules() -> list[dict]:
    """Rules rejected two or more times (same normalized rule, any lesson id): not proposed again."""
    rule_of: dict[str, str] = {}
    counts: dict[str, int] = {}
    for e in _all_events():
        kind = e["event"].split(".")[1]
        lid = e.get("lesson", "")
        if kind == "proposed":
            rule_of[lid] = e.get("value", {}).get("rule", "")
        elif kind == "rejected" and rule_of.get(lid):
            k = _norm(rule_of[lid])
            counts[k] = counts.get(k, 0) + 1
    return [{"rule": k, "rejections": n} for k, n in counts.items() if n >= 2]


MARKER = re.compile(r"\b(sempre|nunca mais|a partir de agora|de agora em diante|lembra(?:r)?(?: que| de)?|não esquece|"
                    r"from now on|always|never again|remember(?: that|:)?)\b", re.I)
CORRECTION = re.compile(r"^\s*(n[ãa]o[,.! ]|para de|pare de|errado|isso n[ãa]o|n[ãa]o era|n[ãa]o foi isso|"
                        r"no[,.! ]|stop |don'?t |that'?s (not|wrong)|actually|wrong)", re.I)
PRAISE = re.compile(r"\b(perfeito|era isso|ficou [óo]timo|gostei|exatamente|boa[!.]|isso mesmo|"
                    r"perfect|exactly|that'?s it|nice work|love it)\b", re.I)
TOOL_ERR = re.compile(r"(Traceback|command not found|No such file|Permission denied|Error:|FAILED|exit code [1-9])", re.I)
MAX_CHARS = 2000


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def scan(path: str, max_n: int = 30) -> list[dict]:
    """Candidate signals in a Claude Code session JSONL; no LLM, patterns only."""
    out: list[dict] = []
    err_at: int | None = None
    for i, line in enumerate(Path(path).expanduser().read_text(errors="replace").splitlines()):
        if len(out) >= max_n:
            break
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        t = rec.get("type")
        content = (rec.get("message") or {}).get("content")
        if t == "user":
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        c = b.get("content")
                        txt = c if isinstance(c, str) else _text(c)
                        if b.get("is_error") or TOOL_ERR.search(txt[:400]):
                            err_at = i
            text = _text(content).strip()
            if not text or len(text) > MAX_CHARS:
                continue
            kind = "marker" if MARKER.search(text) else "correction" if CORRECTION.search(text) else \
                "praise" if PRAISE.search(text) else None
            if kind:
                out.append({"index": i, "kind": kind, "quote": text[:300]})
        elif t == "assistant" and err_at is not None and i - err_at <= 6:
            text = _text(content).strip()
            if text and len(text) <= MAX_CHARS and re.search(r"\b(workaround|instead|em vez|vou tentar|try|fix)", text, re.I):
                out.append({"index": err_at, "kind": "tool_error", "quote": text[:300]})
                err_at = None
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="retro.py", description="Retro journal: the only writer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("event")
    e.add_argument("value")
    e.add_argument("--lesson")
    e.add_argument("--actor", required=True)
    l = sub.add_parser("lessons")
    l.add_argument("--status")
    sub.add_parser("rejected-rules")
    s = sub.add_parser("scan")
    s.add_argument("jsonl")
    s.add_argument("--max", type=int, default=30)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            print(json.dumps(emit(a.event, json.loads(a.value), a.lesson, a.actor), ensure_ascii=False))
        elif a.cmd == "lessons":
            print(json.dumps(lessons(a.status), ensure_ascii=False, indent=2))
        elif a.cmd == "rejected-rules":
            print(json.dumps(rejected_rules(), ensure_ascii=False, indent=2))
        else:
            for row in scan(a.jsonl, a.max):
                print(json.dumps(row, ensure_ascii=False))
    except (ValueError, OSError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
