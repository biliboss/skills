"""view_state.py (skill thread): the thread view's state, closed as a value object.

The screen a thread agent builds is this shape and nothing else. view.py writes it and checks it on every write;
threadview.py draws it; the SKILL.md points here instead of repeating it. Python 3.9, no dependencies.

  python3 view_state.py check <view.json>      exit 0 when valid, 2 with the problems listed
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import List, Optional

STEP_STATES = ("done", "doing", "blocked", "todo")
LANE_STATES = ("todo", "doing", "done")
ARTIFACT_STATES = ("empty", "ready", "drawing")
WORKER_STATES = ("running", "done", "fail")
TOP_KEYS = {"goal", "stage", "steps", "artifacts", "decision", "pulse", "workers", "url", "updated_at"}


@dataclass(frozen=True)
class Goal:
    """One goal: the title, and the constraint that matters as the subtitle."""
    title: str = ""
    subtitle: str = ""


@dataclass(frozen=True)
class ReadyItem:
    """One line of the Definition of Ready: something that must be true to start the Downstream."""
    text: str
    done: bool = False


@dataclass(frozen=True)
class Stage:
    """The thread's lane. Born in progress in the Upstream (the template); the owner alone moves it Downstream.
    ready is 0-100; with a checklist it is items done / total."""
    upstream: str = "doing"
    downstream: str = "todo"
    ready: int = 0
    checklist: List[ReadyItem] = field(default_factory=list)


@dataclass(frozen=True)
class Step:
    """3-6 steps, the lifecycle in order; done ones collapse on screen."""
    text: str
    state: str = "todo"
    note: str = ""


@dataclass(frozen=True)
class Artifact:
    """An image is a box in the showcase; anything else (skill, domain, PR, card) is a related link line."""
    name: str
    key: str = ""
    state: str = "ready"
    path: str = ""
    url: str = ""
    pct: Optional[int] = None
    wins: int = 0


@dataclass(frozen=True)
class Option:
    """A choice: the agent's confidence; all options sum 100 and the first is the recommended."""
    label: str
    pct: int


@dataclass(frozen=True)
class Key:
    """A fixed key per process edge (a tournament): the same key always walks the same edge."""
    key: str
    label: str
    send: str
    answer: str = ""
    type: bool = False


@dataclass(frozen=True)
class Decision:
    """The screen's ask tool: only when THIS thread waits for the owner."""
    text: str
    cmd: Optional[str] = None
    options: List[Option] = field(default_factory=list)
    keys: List[Key] = field(default_factory=list)
    tournament: str = ""


@dataclass(frozen=True)
class Worker:
    """Work longer than a turn (10 s), one line in Agentes; Hermes subagents are read, not written."""
    id: str
    what: str
    state: str = "running"
    started_at: float = 0.0
    ended_at: Optional[float] = None
    note: str = ""
    pid: Optional[int] = None


@dataclass(frozen=True)
class ViewState:
    goal: Goal = field(default_factory=Goal)
    stage: Stage = field(default_factory=Stage)
    steps: List[Step] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    decision: Optional[Decision] = None
    pulse: str = ""
    workers: List[Worker] = field(default_factory=list)


# The house's Definition of Ready: what is usually true before any Downstream starts. The agent drops what does not
# apply to its thread and adds what is specific to it.
DEFAULT_READY = (
    "domínio desenhado no dev-console (eventos e transições)",
    "widgets de cada evento desenhados",
    "backbrief confirmado pelo dono",
)


def template() -> dict:
    """What every thread is born with: in progress in the Upstream, with the house's Definition of Ready."""
    return {"goal": {"title": "", "subtitle": ""},
            "stage": {"upstream": "doing", "downstream": "todo", "ready": 0,
                      "checklist": [{"text": t, "done": False} for t in DEFAULT_READY]},
            "steps": [], "artifacts": [], "decision": None, "pulse": ""}


def check(v: dict) -> List[str]:
    """The problems in a view state (an empty list means valid)."""
    bad: List[str] = []
    extra = set(v) - TOP_KEYS
    if extra: bad.append(f"unknown keys: {sorted(extra)}")
    sg = v.get("stage") or {}
    for lane in ("upstream", "downstream"):
        if sg.get(lane, "todo") not in LANE_STATES: bad.append(f"stage.{lane} must be one of {LANE_STATES}")
    r = sg.get("ready", 0)
    if not isinstance(r, int) or not 0 <= r <= 100: bad.append("stage.ready must be 0-100")
    if sg.get("downstream", "todo") != "todo" and sg.get("upstream") != "done":
        bad.append("Downstream started with the Upstream not done")
    for c in sg.get("checklist") or []:
        if not c.get("text"): bad.append("checklist item without text")
    for s in v.get("steps") or []:
        if s.get("state", "todo") not in STEP_STATES: bad.append(f"step {s.get('text', '')!r}: state must be one of {STEP_STATES}")
    for a in v.get("artifacts") or []:
        if a.get("state", "ready") not in ARTIFACT_STATES: bad.append(f"artifact {a.get('name', '')!r}: bad state")
    d = v.get("decision")
    if d:
        if not d.get("text") and not d.get("keys"): bad.append("decision without text")
        opts = [o for o in d.get("options") or [] if isinstance(o, dict)]
        if opts and sum(o.get("pct", 0) for o in opts) != 100: bad.append("decision options must sum 100")
    for w in v.get("workers") or []:
        if w.get("state", "running") not in WORKER_STATES: bad.append(f"worker {w.get('id', '')!r}: bad state")
    return bad


def main(a: List[str]) -> int:
    if len(a) != 2 or a[0] != "check":
        print(__doc__); return 2
    with open(a[1]) as f: problems = check(json.load(f))
    for p in problems: print(f"view_state: {p}", file=sys.stderr)
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
