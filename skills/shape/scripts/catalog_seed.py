# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Real numbers from the house journals, for the resource catalog (resources.json). Prints JSON; never invents:
a key missing here means the catalog keeps its `estimate`.

  uv run --script catalog_seed.py
Reads (each optional): ~/.local/share/{costs,tasks,brainstorm}/events.jsonl and the Hermes delegation transcripts
~/.hermes/profiles/bili/cache/delegation/live/*/task-*.log (`final | status=completed duration=<s>s`).
"""
from __future__ import annotations

import glob
import json
import re
import statistics
from datetime import datetime
from pathlib import Path

SHARE = Path("~/.local/share").expanduser()


def rows(name: str) -> list[dict]:
    p = SHARE / name / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def subagent_minutes() -> dict:
    pat = str(Path("~/.hermes/profiles/bili/cache/delegation/live").expanduser() / "*/task-*.log")
    d = []
    for f in glob.glob(pat):
        m = re.search(r"status=completed duration=([\d.]+)s", Path(f).read_text(errors="ignore"))
        if m:
            d.append(float(m.group(1)) / 60)
    return {"n": len(d), "avg_min": round(statistics.mean(d), 1) if d else None, "path": pat}


def owner_minutes_by_domain() -> dict:
    out: dict[str, list[float]] = {}
    for e in rows("costs"):
        if e["event"] == "time_entry.stopped":
            out.setdefault(e["value"].get("domain", "?"), []).append(e["value"]["seconds"] / 60)
    return {k: {"n": len(v), "avg_min": round(statistics.mean(v), 1)} for k, v in out.items()}


def brainstorm_minutes() -> dict:
    start, d = {}, []
    for e in rows("brainstorm"):
        if e["event"] == "session.started":
            start[e["session"]] = ts(e["at"])
        elif e["event"] == "session.finished" and e["session"] in start:
            d.append((ts(e["at"]) - start[e["session"]]).total_seconds() / 60)
    return {"n": len(d), "avg_min": round(statistics.mean(d), 1) if d else None}


def backbrief_owner_minutes() -> dict:
    """Owner time on a backbrief: taught_back -> confirmed, same task, capped at 30 min (a gap is not attention)."""
    tb, d = {}, []
    for e in rows("tasks"):
        t = e.get("task_id")
        if e["event"] == "understanding.taught_back":
            tb[t] = ts(e["at"])
        elif e["event"] == "understanding.confirmed" and t in tb:
            m = (ts(e["at"]) - tb[t]).total_seconds() / 60
            if 0 <= m <= 30:
                d.append(m)
    return {"n": len(d), "avg_min": round(statistics.mean(d), 1) if d else None}


if __name__ == "__main__":
    print(json.dumps({"subagent": subagent_minutes(), "owner_by_domain": owner_minutes_by_domain(),
                      "brainstorm": brainstorm_minutes(), "backbrief": backbrief_owner_minutes()},
                     ensure_ascii=False, indent=2))
