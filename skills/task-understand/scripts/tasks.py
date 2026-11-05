# /// script
# requires-python = ">=3.11"
# ///
"""Tasks: someone explains a task, and at the end the one who received it repeats it back as they understood it.

The practice is teach-back ("explain it back in your own words", from health literacy) and the loop it closes is
closed-loop communication (aviation, crew resource management). Task is the most universal name for a piece of work
given to someone: a to-do at home, an assignment at school, a ticket in a software team.

Storage: one global append-only JSONL shared by every agent, ~/.local/share/tasks/events.jsonl (override TASKS_DIR).

    uv run --script tasks.py emit task.explained '{"title": ..., "text": ..., "to": ...}' --actor gabriel
    uv run --script tasks.py emit understanding.taught_back '{"text": ...}' --task <task_id> --actor bili-local
    uv run --script tasks.py use-learnings --task <task_id>        # learning.used, before repeating back
    uv run --script tasks.py feedback --task <task_id> --text "..."  # feedback.given + downscore; prints the 3 styles
    uv run --script tasks.py options --task <task_id> '{"direto": "...", "passo-a-passo": "...", "exemplo": "..."}'
    uv run --script tasks.py choose --task <task_id> --option <option_id>   # option.chosen + style score
    uv run --script tasks.py styles                                # scores and the default style
    uv run --script tasks.py execute --task <task_id> [--cwd <folder>]   # only after understanding.confirmed
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_DIR = "~/.local/share/tasks"
CONFIG = Path(os.environ.get("TASKS_CONFIG", "~/.config/tasks/config.json")).expanduser()
# Who executes a confirmed task. Default: the claude-code skill's print mode, on the mukutu account, with Sonnet.
# Override in CONFIG ({"execute": {"command": [...], "env": {...}}}); {prompt} is replaced by the task's prompt.
# Following the claude-code skill: print mode, a cap on turns, only the tools the work needs, its own git worktree
# (so edits never land on a shared checkout), and JSON output (result, cost, turns, session id for --resume).
# {prompt} is the task's prompt, {task} the first 8 characters of its id.
DEFAULT_EXECUTOR = {
    "command": ["claude", "-p", "--model", "sonnet", "--max-turns", "30", "--output-format", "json",
                "--allowedTools", "Read,Edit,Write,Glob,Grep,Bash(uv run *),Bash(git status*),Bash(git diff*)",
                "--worktree", "task-{task}", "{prompt}"],
    "env": {"CLAUDE_CONFIG_DIR": "~/.claude-mukutu"},
}

# The three fixed styles of a repetition. Each has a version: change the guide, bump the version, and the style starts
# again from zero (scores of an older version do not count). The default style is the one with the highest score.
STYLES = {
    "direto": {"version": 1, "guide": "Uma frase só: o resultado que você vai entregar, sem rodeio."},
    "passo-a-passo": {"version": 1, "guide": "Lista curta e numerada dos passos que você vai dar, na ordem."},
    "exemplo": {"version": 1, "guide": "Um parágrafo curto que mostra como ficará pronto, com um exemplo concreto."},
}

EVENTS = {
    # Alguém explicou uma tarefa a outra pessoa, do jeito dele e com o tempo que ela pedia; depois do entendimento
    # confirmado, quem recebeu executou a tarefa.
    "task": {"explain": "explained", "execute": "executed"},
    # No fim, quem recebeu a tarefa repetiu tudo o que ouviu, do jeito que entendeu (o teach-back), e quem explicou
    # confirmou que bate.
    "understanding": {"teach_back": "taught_back", "confirm": "confirmed"},
    # A resposta de quem explicou foi um ajuste, não uma confirmação: virou aprendizado, um evento de valor. Antes de
    # repetir, quem recebeu procura os aprendizados que servem e usa (o uso também é um evento de valor).
    "learning": {"record_learning": "recorded", "use_learning": "used"},
    # Quem explicou disse que a repetição não ficou boa.
    "feedback": {"give_feedback": "given"},
    # Nasceram três opções de repetição, cada uma numa versão com o nome de um estilo (rascunho: só no grafo).
    "option": {"generate_options": "generated", "choose": "chosen"},
    # O estilo ganhou pontos quando a opção dele foi escolhida (score) e perdeu quando a repetição dele recebeu
    # feedback (downscore); o de maior pontuação vira o padrão (rascunho: só no grafo).
    "style": {"score": "scored", "downscore": "scored"},
}

class Method(StrEnum):
    """How the work ran."""

    PRINT = "print"  # one shot: the harness gets the task, runs and exits
    INTERACTIVE = "interactive"  # a session someone can follow and steer
    BY_HAND = "by_hand"  # the agent did it itself, no executor


class Harness(StrEnum):
    """The agent harness that ran it."""

    CLAUDE_CODE = "claude-code"
    HERMES = "hermes"
    PI = "pi"


class Model(StrEnum):
    """The model family."""

    SONNET = "sonnet"
    OPUS = "opus"
    HAIKU = "haiku"


class Effort(StrEnum):
    """How hard the model was asked to think."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Delivery(StrEnum):
    """Where the work landed."""

    PR_OPEN = "pr_open"
    PR_CLOSED = "pr_closed"
    MAIN = "main"  # straight on main, no pull request


@dataclass(frozen=True)
class Picture:
    """One image and the sentence that says what it shows."""

    src: str
    caption: str


@dataclass(frozen=True)
class BeforeAfter:
    """How it was and how it is, side by side."""

    title: str
    before: Picture
    after: Picture


@dataclass(frozen=True)
class Journey:
    """The steps of the work, in order, one picture each."""

    title: str
    steps: tuple[Picture, ...]


class PullRequestState(StrEnum):
    """Where a pull request stands."""

    OPEN = "open"
    CLOSED = "closed"  # closed without merge
    MERGED = "merged"


@dataclass(frozen=True)
class Commit:
    """One commit the work produced."""

    sha: str
    message: str
    repo: str  # owner/name


@dataclass(frozen=True)
class PullRequest:
    """The pull request that carries the work."""

    number: int
    url: str
    state: PullRequestState


@dataclass(frozen=True)
class SessionRef:
    """Where the agent's session can be found again: its id (to resume) and its log."""

    harness: Harness
    id: str | None  # the harness's session id, when it gave one
    log: str  # path of the session log


@dataclass(frozen=True)
class ExecutionResult:
    """How a task was executed and what it delivered."""

    text: str  # what the execution answered, a report for people (markdown, headings, mermaid)
    method: Method
    harness: Harness
    model: Model
    effort: Effort
    cycle_time_s: int  # from the confirmation to the end of the run, in seconds
    delivery: Delivery
    session: SessionRef
    pull_request: PullRequest | None = None  # when the work went through one
    commits: tuple[Commit, ...] = ()
    before_afters: tuple[BeforeAfter, ...] = ()  # N comparisons
    journeys: tuple[Journey, ...] = ()  # N journeys


# Which value object each event carries (the dev-console's Code shows it with the event).
VALUES = {"task.executed": "ExecutionResult"}

# The edges are the commands (UML statechart transitions); a target may name its edge's command when one event has
# several ({"style.scored": "downscore"}). Drafts are drawn before they are built.
TRANSITIONS = {
    "task.explained": ["learning.used"],
    "learning.used": ["understanding.taught_back"],
    "understanding.taught_back": ["learning.recorded", "feedback.given"],  # the Human confirms (INITIAL)
    "learning.recorded": ["learning.used"],
    "feedback.given": {"option.generated": "generate_options", "style.scored": "downscore"},
    "option.generated": ["option.chosen"],
    "option.chosen": {"style.scored": "score"},
    "understanding.confirmed": ["task.executed"],
}


def _project(events: list[dict]) -> dict | None:
    state = None
    for e in events:
        event, value = e["event"], e["value"]
        if event == "task.explained":
            state = {
                # the task's id
                "id": e["task_id"],
                # what has to be done, in one line
                "title": value["title"],
                # the task as it was explained
                "text": value["text"],
                # each teach-back, in the receiver's words
                "teach_backs": [],
                # each adjustment of whoever explained, verbatim
                "learnings": [],
                # the three styled repetitions offered after a feedback, not chosen yet
                "options": [],
                # the style of the current repetition (none when it was not styled)
                "style": None,
                # what the execution answered, once executed
                "result": None,
                # explained, taught_back, confirmed or executed
                "status": "explained",
                # when the task last moved
                "updated_at": e["at"],
            }
        if state is None:
            continue
        if event == "understanding.taught_back":
            state["teach_backs"].append(value["text"])
            state["style"] = value.get("style")
            state["options"] = []
            state["status"] = "taught_back"
        elif event == "option.generated":
            state["options"].append({"id": e["id"], "style": value["style"], "version": value["version"], "text": value["text"]})
        elif event == "option.chosen":
            # the chosen option becomes the repetition the Human is asked to confirm
            state["teach_backs"].append(value["text"])
            state["style"] = value["style"]
            state["options"] = []
            state["status"] = "taught_back"
        elif event == "learning.recorded":
            state["learnings"].append(value["text"])
        elif event == "understanding.confirmed":
            state["status"] = "confirmed"
        elif event == "task.executed":
            state["result"] = value["text"]
            state["status"] = "executed"
        state["updated_at"] = e["at"]
    return state


class TasksJournal:
    """The global journal: append-only JSONL, one line per event, shared by every agent on this machine."""

    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory or os.environ.get("TASKS_DIR", DEFAULT_DIR)).expanduser()
        self.path = self.directory / "events.jsonl"

    def emit(self, event: str, value: dict, task_id: str | None = None, *, actor: str | None = None) -> dict:
        """Append one event. task.explained opens a Task (task_id generated when absent); the rest need its id."""
        category, _, verb = event.partition(".")
        if verb not in EVENTS.get(category, {}).values():
            raise ValueError(f"unknown event: {event}")
        if not isinstance(value, dict) or not value.get("text"):
            raise ValueError("value must be an object with text")
        if event in ("option.generated", "option.chosen", "style.scored"):
            if value.get("style") not in STYLES:
                raise ValueError(f"{event} needs a style, one of {list(STYLES)}")
            value = {**value, "version": value.get("version", STYLES[value["style"]]["version"])}
        if event == "style.scored" and not isinstance(value.get("delta"), int):
            raise ValueError("style.scored needs an integer delta (+ score, - downscore)")
        if event == "option.chosen" and not value.get("option_id"):
            raise ValueError("option.chosen needs option_id")
        if event == "task.explained":
            if not value.get("title"):
                raise ValueError("task.explained needs a title")
            task_id = task_id or str(uuid4())
        elif not task_id:
            raise ValueError("task_id is required except for task.explained")
        record = {"id": str(uuid4()), "event": event,
                  "at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                  "actor": actor or os.environ.get("TASKS_ACTOR", "unknown"), "task_id": task_id, "value": value}
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def read(self, query: dict | None = None) -> Any:
        """{} -> every Task; {"id"} -> one; {"id", "history"} -> its events; {"event"} -> that type; {"history"} -> all."""
        query = query or {}
        text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
        if "id" in query:
            matches = [e for e in events if e["task_id"] == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for e in events:
            groups.setdefault(e["task_id"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]



def _words(text: str) -> set[str]:
    import re

    return {w for w in re.findall(r"\w{4,}", text.lower())}


def style_scores(journal: TasksJournal | None = None) -> dict[str, int]:
    """Points per style, counting only the events of its current version: score (+) and downscore (-) add up."""
    scores = {name: 0 for name in STYLES}
    for e in (journal or TasksJournal()).read({"event": "style.scored"}):
        v = e["value"]
        if v["style"] in scores and v.get("version") == STYLES[v["style"]]["version"]:
            scores[v["style"]] += v["delta"]
    return scores


def default_style(journal: TasksJournal | None = None) -> str:
    """The style with the highest score; a tie goes to the first one declared in STYLES."""
    scores = style_scores(journal)
    return max(STYLES, key=lambda name: scores[name])


def use_learnings(task_id: str, *, actor: str | None = None) -> dict | None:
    """Find the learnings that apply to this task and record learning.used; None when nothing applies.

    A learning applies when it was recorded on this task, or on another one that shares at least two words (4+
    letters) with this task's title and text. A learning already used on this task is not used again."""
    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state:
        raise ValueError(f"no task {task_id}")
    history = journal.read({"history": True})
    used = {i for e in history if e["event"] == "learning.used" and e["task_id"] == task_id for i in e["value"]["learning_ids"]}
    mine = _words(state["title"] + " " + state["text"])
    found = [e for e in history if e["event"] == "learning.recorded" and e["id"] not in used
             and (e["task_id"] == task_id or len(mine & _words(e["value"]["text"])) >= 2)]
    if not found:
        return None
    text = "\n".join(f"- {e['value']['text']}" for e in found)
    return journal.emit("learning.used", {"text": text, "learning_ids": [e["id"] for e in found]}, task_id, actor=actor)


def feedback(task_id: str, text: str, *, actor: str | None = None) -> dict:
    """The Human said the repetition was not good: record feedback.given, downscore the style it used, and return
    the three styles (with the default first) for the agent to write one repetition each (see generate_options)."""
    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state or not state["teach_backs"]:
        raise ValueError(f"task {task_id} has no repetition to give feedback on")
    given = journal.emit("feedback.given", {"text": text, "style": state["style"]}, task_id, actor=actor)
    if state["style"]:
        journal.emit("style.scored", {"text": f"downscore: feedback on {state['style']}", "style": state["style"], "delta": -1},
                     task_id, actor="tasks")
    order = [default_style(journal)] + [n for n in STYLES if n != default_style(journal)]
    return {"feedback": given, "styles": [{"style": n, **STYLES[n]} for n in order]}


def generate_options(task_id: str, texts: dict[str, str], *, actor: str | None = None) -> list[dict]:
    """Record option.generated for each of the three styles, one repetition each (all three are required)."""
    if set(texts) != set(STYLES):
        raise ValueError(f"one text per style is required: {list(STYLES)}")
    journal = TasksJournal()
    return [journal.emit("option.generated", {"text": texts[n], "style": n}, task_id, actor=actor) for n in STYLES]


def choose(task_id: str, option_id: str, *, actor: str | None = None) -> dict:
    """The Human picked one option: record option.chosen and score its style (+1)."""
    journal = TasksJournal()
    state = journal.read({"id": task_id})
    option = next((o for o in (state or {}).get("options", []) if o["id"] == option_id), None)
    if not option:
        raise ValueError(f"no pending option {option_id} on task {task_id}")
    chosen = journal.emit("option.chosen", {"text": option["text"], "style": option["style"], "version": option["version"],
                                            "option_id": option_id}, task_id, actor=actor)
    journal.emit("style.scored", {"text": f"score: {option['style']} chosen", "style": option["style"], "delta": 1,
                                  "version": option["version"]}, task_id, actor="tasks")
    return chosen


def executor() -> dict:
    """The configured executor (CONFIG's "execute"), or the default one."""
    if CONFIG.exists():
        return {**DEFAULT_EXECUTOR, **json.loads(CONFIG.read_text()).get("execute", {})}
    return DEFAULT_EXECUTOR


def execute(task_id: str, cwd: str | None = None, *, actor: str | None = None) -> dict:
    """Run the executor on a confirmed task and record task.executed with what it answered."""
    import subprocess

    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state:
        raise ValueError(f"no task {task_id}")
    if state["status"] != "confirmed":
        raise ValueError(f"task {task_id} is {state['status']}: only a confirmed understanding is executed")
    prompt = (f"Tarefa: {state['title']}\n\nComo foi explicada:\n{state['text']}\n\n"
              f"Como foi entendida (confirmado por quem explicou):\n{state['teach_backs'][-1]}\n\n"
              + ("Ajustes de quem explicou:\n" + "\n".join(f"- {x}" for x in state["learnings"]) + "\n\n" if state["learnings"] else "")
              + "Execute a tarefa e termine com um relato curto do que fez.")
    run = executor()
    env = {**os.environ, **{k: os.path.expanduser(v) for k, v in run.get("env", {}).items()}}
    cmd = [prompt if part == "{prompt}" else part.replace("{task}", task_id[:8]) for part in run["command"]]
    done = subprocess.run(cmd, cwd=cwd or os.getcwd(), env=env, capture_output=True, text=True)
    out = done.stdout.strip()
    extra: dict = {}
    try:  # --output-format json: keep the answer and what it cost
        res = json.loads(out)
        out = res.get("result") or out
        extra = {k: res[k] for k in ("session_id", "num_turns", "total_cost_usd", "subtype") if k in res}
    except (json.JSONDecodeError, AttributeError):
        pass
    answer = (out or done.stderr.strip() or "(sem resposta)")[-4000:]
    return journal.emit("task.executed", {"text": answer, "exit_code": done.returncode, "executor": run["command"][0], **extra},
                        task_id, actor=actor or os.environ.get("TASKS_ACTOR", run["command"][0]))

if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="tasks: emit or read the global journal")
    sub = cli.add_subparsers(dest="cmd", required=True)
    em = sub.add_parser("emit")
    em.add_argument("event")
    em.add_argument("value", help="a JSON object")
    em.add_argument("--task")
    em.add_argument("--actor")
    ex = sub.add_parser("execute", help="run the configured executor on a confirmed task")
    ex.add_argument("--task", required=True)
    ex.add_argument("--cwd")
    ex.add_argument("--actor")
    ul = sub.add_parser("use-learnings", help="record learning.used with the learnings that apply to the task")
    ul.add_argument("--task", required=True)
    ul.add_argument("--actor")
    fb = sub.add_parser("feedback", help="feedback.given + downscore; prints the three styles to write")
    fb.add_argument("--task", required=True)
    fb.add_argument("--text", required=True)
    fb.add_argument("--actor")
    op = sub.add_parser("options", help="option.generated x3, from a JSON {style: repetition}")
    op.add_argument("texts")
    op.add_argument("--task", required=True)
    op.add_argument("--actor")
    ch = sub.add_parser("choose", help="option.chosen + style score")
    ch.add_argument("--task", required=True)
    ch.add_argument("--option", required=True)
    ch.add_argument("--actor")
    sub.add_parser("styles", help="scores per style and the default one")
    rd = sub.add_parser("read")
    rd.add_argument("--task")
    args = cli.parse_args()
    journal = TasksJournal()
    out = lambda v: print(json.dumps(v, ensure_ascii=False, indent=2))  # noqa: E731
    if args.cmd == "use-learnings":
        out(use_learnings(args.task, actor=args.actor) or {"used": None, "note": "no learning applies"})
    elif args.cmd == "feedback":
        out(feedback(args.task, args.text, actor=args.actor))
    elif args.cmd == "options":
        out(generate_options(args.task, json.loads(args.texts), actor=args.actor))
    elif args.cmd == "choose":
        out(choose(args.task, args.option, actor=args.actor))
    elif args.cmd == "styles":
        out({"scores": style_scores(), "default": default_style(), "styles": STYLES})
    elif args.cmd == "execute":
        print(json.dumps(execute(args.task, args.cwd, actor=args.actor), ensure_ascii=False))
    elif args.cmd == "emit":
        print(json.dumps(journal.emit(args.event, json.loads(args.value), args.task, actor=args.actor), ensure_ascii=False))
    else:
        print(json.dumps(journal.read({"id": args.task} if args.task else {}), ensure_ascii=False, indent=2))
