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
    uv run --script tasks.py models                                # the model registry, and which ones pi sees now
    uv run --script tasks.py execute --task <task_id> [--models sonnet,glm] [--cwd <repo>]
                                                                   # pi in parallel, one worktree per model;
                                                                   # only after understanding.confirmed
    uv run --script tasks.py verify --task <task_id> [--model sonnet] [--cwd <dir>] [--executed <event_id>]
                                                                   # IV&V: pi in a fresh context checks the delivery
    uv run --script tasks.py deliver --task <task_id> --kind pr|direct|none [--url <link>] [--text "..."]
    uv run --script tasks.py merge --task <task_id> [--url <link>]  # records pull_request.merged (gh pr merge is yours)
    uv run --script tasks.py request-review --task <task_id> --text "<why>"
    uv run --script tasks.py clean --task <task_id> [--repo <path>] [--branch <b>]
                                                                   # after the merge: checks the worktree, the remote
                                                                   # branch and the open PR are gone (removes what is
                                                                   # left, never forced), then records workspace.cleaned
    uv run --script tasks.py branch --task <task_id> --slug <slug> # the branch name every branch of the skill takes:
                                                                   # task/<id8>-<slug>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_DIR = "~/.local/share/tasks"


def _config() -> dict:
    """~/.config/tasks/config.json (override with TASKS_CONFIG), when it exists and parses."""
    path = Path(os.environ.get("TASKS_CONFIG", "~/.config/tasks/config.json")).expanduser()
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


# The models a confirmed task may run on, each on one of our flat plans: the mukutu Claude subscription (pi's
# claude-bridge provider; the account is chosen by CLAUDE_CONFIG_DIR) or our GLM Coding Plan (provider zai). An env
# value that starts with "@" is a recipe: the named file's content, stripped, goes to the child process's env only
# (the GLM key is read from ~/glm_token into ZAI_API_KEY and never printed, logged or committed). Per-token providers
# (OpenRouter, ~anthropic/...) are refused. Override and extend in ~/.config/tasks/config.json, keys "models" and
# "default_model"; this replaced the old "execute" command override of 0.4.0-0.10.0 (pi is the only executor now).
FLAT_PLANS = {"claude-bridge": "mukutu-claude", "zai": "glm-coding-plan"}
DEFAULT_MODELS = {
    "sonnet": {"model": "claude-bridge/claude-sonnet-5-5", "plan": "mukutu-claude",
               "env": {"CLAUDE_CONFIG_DIR": "~/.claude-mukutu"}, "name": "Claude Sonnet (mukutu)"},
    "glm": {"model": "zai/glm-5.3", "plan": "glm-coding-plan", "env": {"ZAI_API_KEY": "@~/glm_token"},
            "name": "GLM 5.3 (coding plan)"},
    "glm-flash": {"model": "zai/glm-5.3-flash", "plan": "glm-coding-plan", "env": {"ZAI_API_KEY": "@~/glm_token"},
                  "name": "GLM 5.3 Flash (coding plan)"},
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
    # confirmado, quem recebeu executou a tarefa. Um contexto novo, de fora, que só conhece o pedido confirmado e a
    # entrega, verificou o trabalho (verificação independente, IV&V) e gravou as checagens com as evidências; se não
    # passou, a tarefa volta a ser executada. Depois veio a entrega, com o tipo: PR, mudança direta (uma issue criada,
    # um card movido) ou nenhuma; o PR é um tipo de entrega, não um passo obrigatório.
    "task": {"explain": "explained", "execute": "executed", "verify": "verified", "deliver": "delivered"},
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
    # A entrega foi um PR, e quem explicou decidiu pelo peso do trabalho, com a recomendada primeiro: protótipo ou
    # experimento, o merge direto; produto ou cliente, pedir a revisão antes, e a tarefa volta a ser executada (deixar
    # aberto não é evento). Os nomes são os do GitHub.
    "pull_request": {"merge": "merged", "request_review": "review_requested"},
    # Depois do merge, o espaço de trabalho foi limpo de verdade: nenhum worktree da tarefa, nenhuma branch remota,
    # nenhum PR aberto da branch. Só então a tarefa está feita (merge sem limpeza deixa lixo para o próximo agente).
    "workspace": {"clean": "cleaned"},
}

class Method(StrEnum):
    """How the work ran."""

    PRINT = "print"  # one shot: the harness gets the task, runs and exits
    INTERACTIVE = "interactive"  # a session someone can follow and steer
    BY_HAND = "by_hand"  # the agent did it itself, no executor
    PI = "pi"  # a pi run (0.11.0, `execute` per model); the journal also carries it as method
    SPAWN = "spawn"  # a Hermes profile run by `hermes.sh spawn` (hermes skill)


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
class Check:
    """One thing the independent verifier checked: what, how, the evidence it saw and whether it held."""

    what: str
    how: str = ""
    evidence: str = ""
    passed: bool = False


@dataclass(frozen=True)
class Verification:
    """What the independent verification (IV&V) found: a fresh context, only the request and the delivery."""

    text: str  # a short summary
    passed: bool
    checks: tuple[Check, ...] = ()
    model: str = ""  # the registry id that verified
    provider: str = ""
    plan: str = ""
    duration_s: int | None = None
    exit_code: int | None = None


@dataclass(frozen=True)
class TaskDelivery:
    """Where the work landed once it was verified: a pull request, a direct change, or nothing to hand over."""

    text: str
    kind: str  # pr | direct | none
    url: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    """How a task was executed and what it delivered."""

    text: str  # what the execution answered, a report for people (markdown, headings, mermaid)
    method: Method | None = None
    harness: Harness | None = None
    model: str | None = None  # a registry id (sonnet, glm, glm-flash) or a Model family, in older runs
    effort: Effort | None = None
    cycle_time_s: int | None = None  # from the confirmation to the end of the run, in seconds
    delivery: Delivery | None = None
    session: SessionRef | None = None
    pull_request: PullRequest | None = None  # when the work went through one
    commits: tuple[Commit, ...] = ()
    before_afters: tuple[BeforeAfter, ...] = ()  # N comparisons
    journeys: tuple[Journey, ...] = ()  # N journeys
    # a pi run (0.11.0, one per model): the flat plan that rode it and what the run itself reports
    provider: str = ""  # pi's provider (claude-bridge, zai)
    plan: str = ""  # the flat plan (mukutu-claude, glm-coding-plan)
    exit_code: int | None = None
    duration_s: int | None = None  # the run itself, in seconds
    worktree: str = ""
    branch: str = ""
    turns: int | None = None
    tokens: int | None = None
    cost_usd: float | None = None  # None on a flat plan: no per-token cost to report
    # what came after the run (0.13.0), attached by outcome_of from the events that follow it
    verification: Verification | None = None
    delivered: TaskDelivery | None = None


# Which value object each event carries (the dev-console's Code shows it with the event).
VALUES = {"task.executed": "ExecutionResult", "task.verified": "Verification", "task.delivered": "TaskDelivery"}

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
    "task.executed": ["task.verified"],
    "task.verified": ["task.delivered", "task.executed"],  # did not pass: executed again (another executor or by hand)
    # A delivered PR: the Human merges it or asks for a review (an INITIAL edge would hide a whole category from the
    # derived graph, so the decision hangs off task.delivered); a review goes back to execution.
    "task.delivered": ["pull_request.merged", "pull_request.review_requested"],
    "pull_request.review_requested": ["task.executed"],
    "pull_request.merged": ["workspace.cleaned"],
}


DELIVERY_KINDS = ("pr", "direct", "none")  # a PR is one kind of delivery, not a required step

MEDIA_DIR = Path(os.environ.get("TASKS_DIR", DEFAULT_DIR)).expanduser() / "media"  # pictures of executed tasks


def result_from(value: dict) -> ExecutionResult | None:
    """The ExecutionResult a task.executed value carries, or None when the run recorded only its text (older runs)."""
    full = {"method", "harness", "model", "effort", "cycle_time_s", "delivery"} <= value.keys()
    pi = {"exit_code", "worktree"} <= value.keys()  # a pi run (0.11.0), one per model
    if not full and not pi:
        return None
    pic = lambda p: Picture(p["src"], p.get("caption", ""))  # noqa: E731
    pr = value.get("pull_request")
    if isinstance(pr, str):  # older writers kept just the URL: the number is its tail, the state what the delivery says
        tail = pr.rstrip("/").rsplit("/", 1)[-1]
        closed = "fechado" in str(value.get("delivery", "")).lower() or value.get("delivery") == "pr_closed"
        pr = {"number": int(tail) if tail.isdigit() else 0, "url": pr, "state": "closed" if closed else "open"}
    s = value.get("session")
    s = s if isinstance(s, dict) else {}

    def one_of(enum, key):  # a field older runs always carried; a pi run may not have it
        if key not in value:
            return None
        try:
            return enum(value[key])
        except ValueError:  # a value an older or newer writer used ("claude-code" as a method): kept as the text it is, never a 500
            return value[key]

    def harness_of(name):  # a Harness, or the text an older writer used
        try:
            return Harness(name)
        except ValueError:
            return name

    def model_of(key):  # a Model family of the older runs, or the registry id as-is (glm, glm-flash, one from config)
        try:
            return Model(value[key])
        except ValueError:
            return value[key]

    return ExecutionResult(
        text=value.get("text", ""), method=one_of(Method, "method"), harness=one_of(Harness, "harness"),
        model=model_of("model") if "model" in value else None, effort=one_of(Effort, "effort"),
        cycle_time_s=int(value["cycle_time_s"]) if "cycle_time_s" in value else None,
        delivery=one_of(Delivery, "delivery"),
        session=SessionRef(harness_of(s.get("harness", value["harness"])), s.get("id"), s.get("log", "")) if full else None,
        pull_request=PullRequest(pr["number"], pr["url"], PullRequestState(pr["state"])) if pr else None,
        commits=tuple(Commit(c["sha"], c["message"], c["repo"]) for c in value.get("commits", [])),
        before_afters=tuple(BeforeAfter(b["title"], pic(b["before"]), pic(b["after"])) for b in value.get("before_afters", [])),
        journeys=tuple(Journey(j["title"], tuple(pic(x) for x in j["steps"])) for j in value.get("journeys", [])),
        provider=value.get("provider", ""), plan=value.get("plan", ""), exit_code=value.get("exit_code"),
        duration_s=value.get("duration_s"), worktree=value.get("worktree", ""), branch=value.get("branch", ""),
        turns=value.get("turns"), tokens=value.get("tokens"), cost_usd=value.get("cost_usd"),
    )


def verification_from(value: dict) -> Verification:
    """The Verification a task.verified value carries."""
    return Verification(
        text=value.get("text", ""), passed=bool(value.get("passed")),
        checks=tuple(Check(str(c.get("what", "")), str(c.get("how", "")), str(c.get("evidence", "")),
                           bool(c.get("passed"))) for c in value.get("checks") or [] if isinstance(c, dict)),
        model=value.get("model", ""), provider=value.get("provider", ""), plan=value.get("plan", ""),
        duration_s=value.get("duration_s"), exit_code=value.get("exit_code"))


def outcome_of(history: list[dict]) -> tuple[ExecutionResult | None, dict | None]:
    """The task's last run with what came after it: its ExecutionResult carrying the verification and the delivery
    that followed it, and its task.executed event ((None, event) for a run that recorded only its text, (None, None)
    when it never ran). A later run starts over: it has no verification yet."""
    from dataclasses import replace

    at = next((i for i in range(len(history) - 1, -1, -1) if history[i]["event"] == "task.executed"), None)
    if at is None:
        return None, None
    run = history[at]
    x = result_from(run["value"])
    if x is None:
        return None, run
    verified = next((verification_from(e["value"]) for e in reversed(history[at:]) if e["event"] == "task.verified"), None)
    d = next((e["value"] for e in reversed(history[at:]) if e["event"] == "task.delivered"), None)
    delivered = TaskDelivery(d.get("text", ""), d.get("kind", "none"), d.get("url", "")) if d else None
    return replace(x, verification=verified, delivered=delivered), run


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
                # the domain the task is about (its dev-console slug), when it names one
                "domain": value.get("domain"),
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
                # the last independent verification of the last run: {text, passed, checks, model}, once verified
                "verification": None,
                # how the work was handed over: {kind, url, text}, once delivered
                "delivery": None,
                # each request of a review on a delivered PR, verbatim
                "review_requests": [],
                # explained, taught_back, confirmed, executed, verified, delivered, merged or done (merged and the
                # workspace cleaned: workspace.cleaned); a verification that did
                # not pass, and a review requested on the PR, put the task back at confirmed (execute runs it again)
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
            state["verification"] = state["delivery"] = None  # a new run starts over
            state["status"] = "executed"
        elif event == "task.verified":
            state["verification"] = {"text": value["text"], "passed": bool(value.get("passed")),
                                     "checks": value.get("checks") or [], "model": value.get("model")}
            state["status"] = "verified" if value.get("passed") else "confirmed"
        elif event == "task.delivered":
            state["delivery"] = {"text": value["text"], "kind": value.get("kind", "none"), "url": value.get("url", "")}
            state["status"] = "delivered"
        elif event == "pull_request.merged":
            state["status"] = "merged"
        elif event == "workspace.cleaned":
            state["status"] = "done"
        elif event == "pull_request.review_requested":
            state["review_requests"].append(value["text"])
            state["verification"] = state["delivery"] = None
            state["status"] = "confirmed"
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
        if event == "workspace.cleaned" and not value.get("branch"):
            raise ValueError("workspace.cleaned needs the branch it cleaned")
        if event in ("option.generated", "option.chosen", "style.scored"):
            if value.get("style") not in STYLES:
                raise ValueError(f"{event} needs a style, one of {list(STYLES)}")
            value = {**value, "version": value.get("version", STYLES[value["style"]]["version"])}
        if event == "style.scored" and not isinstance(value.get("delta"), int):
            raise ValueError("style.scored needs an integer delta (+ score, - downscore)")
        if event == "task.verified" and not isinstance(value.get("passed"), bool):
            raise ValueError("task.verified needs passed (true or false)")
        if event == "task.delivered" and value.get("kind") not in DELIVERY_KINDS:
            raise ValueError(f"task.delivered needs a kind, one of {list(DELIVERY_KINDS)}")
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


def models_registry() -> dict[str, dict]:
    """The MODELS registry: the defaults of this file, overridden and extended by config's "models"."""
    cfg = {k: v for k, v in (_config().get("models") or {}).items() if isinstance(v, dict)}
    out = {mid: {**spec, **cfg.get(mid, {})} for mid, spec in DEFAULT_MODELS.items()}
    out.update({mid: entry for mid, entry in cfg.items() if mid not in out and entry.get("model")})
    return out


def default_model() -> str:
    """The recommended model's id: config's default_model, or "sonnet"."""
    return _config().get("default_model") or "sonnet"


def resolve_model(mid: str) -> dict:
    """One registry entry resolved for pi ({id, model, provider, plan, env, name}); per-token providers are refused."""
    spec = models_registry().get(mid)
    if not spec or not spec.get("model"):
        raise ValueError(f"modelo desconhecido: {mid} (conheço {sorted(models_registry())})")
    provider = str(spec["model"]).partition("/")[0]
    if provider not in FLAT_PLANS:  # OpenRouter and any per-token provider: never on this skill's runs
        raise ValueError(f"{mid} ({spec['model']}) cobra por token ({provider}): recusado — esta skill só roda nos "
                         f"planos flat {', '.join(f'{p} ({plan})' for p, plan in FLAT_PLANS.items())}")
    return {"id": mid, "model": str(spec["model"]), "provider": provider,
            "plan": spec.get("plan") or FLAT_PLANS[provider], "env": spec.get("env") or {},
            "name": spec.get("name") or str(spec["model"])}


def _model_env(spec: dict) -> dict[str, str]:
    """A model's env, only for the child process: literals (~ expanded) and "@<file>" recipes (the file's content,
    stripped; the GLM key never touches this process's env, a log or the console)."""
    env = {}
    for key, value in (spec.get("env") or {}).items():
        if isinstance(value, str) and value.startswith("@"):
            path = Path(value[1:]).expanduser()
            try:
                env[key] = path.read_text(encoding="utf-8").strip()
            except OSError as e:
                raise RuntimeError(f"o env do modelo precisa do arquivo {path}: {e.strerror or e}") from None
        else:
            env[key] = os.path.expanduser(str(value))
    return env


def models_overview() -> dict:
    """The registry for `tasks.py models`: each model, its plan, and whether pi sees it right now."""
    import subprocess

    out = {}
    for mid, spec in models_registry().items():
        provider, _, name = str(spec.get("model", "")).partition("/")
        entry = {"model": spec.get("model"), "plan": spec.get("plan"), "name": spec.get("name"),
                 "env": spec.get("env") or {}, "refused": provider not in FLAT_PLANS}
        if entry["refused"] or not name:  # a per-token provider never runs, even when pi lists it
            entry["usable"] = False
        else:
            try:  # pi --list-models with the model's env: cheap, no model call
                done = subprocess.run(["pi", "--list-models"], env={**os.environ, **_model_env(spec)},
                                      capture_output=True, text=True, timeout=120)
                entry["usable"] = done.returncode == 0 and any(
                    cols[0] == provider and cols[1] == name for cols in (l.split() for l in done.stdout.splitlines())
                    if len(cols) >= 2)
            except (OSError, subprocess.SubprocessError):
                entry["usable"] = False
        out[mid] = entry
    return {"default": default_model(), "models": out}


def branch_name(task_id: str, slug: str) -> str:
    """The name of every branch the skill creates: task/<id8>-<slug> (the pi runs use the model id as the slug)."""
    import re

    clean = re.sub(r"[^a-z0-9._-]+", "-", slug.strip().lower()).strip("-.")
    if not clean:
        raise ValueError("a branch needs a slug")
    return f"task/{task_id[:8]}-{clean}"


def _worktree_for(repo: Path, id8: str, mid: str) -> tuple[Path, str]:
    """The model's own git worktree, from the repo's HEAD: <repo>/../<repo>.task-<id8>-<model> on branch
    task/<id8>-<model> (reused when it already exists, so a re-run lands on the same branch)."""
    import subprocess

    path = repo.parent / f"{repo.name}.task-{id8}-{mid}"
    branch = branch_name(id8, mid)
    if path.exists():
        return path, branch
    done = subprocess.run(["git", "worktree", "add", str(path), "-b", branch], cwd=repo, capture_output=True, text=True)
    if done.returncode != 0:  # the branch can exist from an earlier run: attach the worktree without creating it
        done = subprocess.run(["git", "worktree", "add", str(path), branch], cwd=repo, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"git worktree add {path}: {done.stderr.strip() or done.stdout.strip()}")
    return path, branch


def _pi_run(spec: dict, prompt: str, repo: Path, id8: str) -> dict:
    """One pi run of the prompt on this model, in its own worktree: what it answered and what it cost."""
    worktree, branch = _worktree_for(repo, id8, spec["id"])
    return _pi_exec(spec, prompt, worktree, branch)


def _pi_exec(spec: dict, prompt: str, worktree: Path, branch: str) -> dict:
    """pi, print mode, fresh context (no session), in this directory: what it answered and what it cost."""
    import subprocess
    import time

    cmd = ["pi", "-p", "--no-session", "--mode", "json", "--model", spec["model"], prompt]
    started = time.monotonic()
    done = subprocess.run(cmd, cwd=worktree, env={**os.environ, **_model_env(spec)}, capture_output=True, text=True)
    run = {"worktree": str(worktree), "branch": branch, "exit_code": done.returncode,
           "duration_s": int(time.monotonic() - started), "turns": 0, "session_id": None, "pi_model": None,
           "tokens": None, "cost_usd": None, "text": "", "answer": ""}
    answer, usage = "", {}
    for line in done.stdout.splitlines():  # pi's --mode json stream: one JSON object per line
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = rec.get("type")
        if kind == "session":
            run["session_id"] = rec.get("id")
        elif kind == "turn_end":
            run["turns"] += 1
        elif kind == "message_end" and (rec.get("message") or {}).get("role") == "assistant":
            m = rec["message"]
            run["pi_model"] = m.get("responseModel") or m.get("model") or run["pi_model"]
            usage = m.get("usage") or usage
            answer = "".join(b.get("text", "") for b in m.get("content", []) if b.get("type") == "text") or answer
    if usage:
        run["tokens"] = usage.get("totalTokens")
        run["cost_usd"] = (usage.get("cost") or {}).get("total")
    run["answer"] = answer  # whole, for the verifier's JSON block
    run["text"] = (answer or done.stderr.strip() or "(sem resposta)")[-4000:]
    return run


def execute(task_id: str, cwd: str | None = None, models: list[str] | None = None, *,
            actor: str | None = None) -> list[dict]:
    """Run pi on a confirmed task, in parallel, one model per worktree, and record one task.executed per model."""
    from concurrent.futures import ThreadPoolExecutor

    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state:
        raise ValueError(f"no task {task_id}")
    if state["status"] != "confirmed":
        raise ValueError(f"task {task_id} is {state['status']}: only a confirmed understanding is executed")
    specs = [resolve_model(m) for m in (models or [default_model()])]  # a refused provider never runs
    history = journal.read({"id": task_id, "history": True})
    failed = next((e["value"] for e in reversed(history)
                   if e["event"] in ("task.verified", "pull_request.review_requested")), None)  # what sent it back
    rework = ""
    if failed and "passed" in failed:  # a verification that did not pass
        bad = [c for c in failed.get("checks") or [] if not c.get("passed")]
        rework = ("A execução anterior não passou na verificação independente; corrija:\n"
                  + ("\n".join(f"- {c.get('what', '')}: {c.get('evidence', '')}" for c in bad) or f"- {failed['text']}")
                  + "\n\n")
    elif failed:  # a review asked for on the PR
        rework = f"A revisão do PR pediu mudanças; corrija:\n- {failed['text']}\n\n"
    prompt = (f"Tarefa: {state['title']}\n\nComo foi explicada:\n{state['text']}\n\n"
              f"Como foi entendida (confirmado por quem explicou):\n{state['teach_backs'][-1]}\n\n"
              + ("Ajustes de quem explicou:\n" + "\n".join(f"- {x}" for x in state["learnings"]) + "\n\n" if state["learnings"] else "")
              + rework + "Execute a tarefa e termine com um relato curto do que fez.")
    repo, id8 = Path(cwd or os.getcwd()).resolve(), task_id[:8]
    with ThreadPoolExecutor(max_workers=len(specs)) as pool:  # "does it work on this model?": one worktree each
        runs = list(pool.map(lambda spec: _pi_run(spec, prompt, repo, id8), specs))
    confirmed = next((e["at"] for e in reversed(history) if e["event"] == "understanding.confirmed"), None)
    now = datetime.now(timezone.utc)
    records = []
    for spec, run in zip(specs, runs):  # one task.executed per model, in the order they were asked for
        value = {"text": run["text"], "model": spec["id"], "provider": spec["provider"], "plan": spec["plan"],
                 "harness": Harness.PI.value, "method": Method.PRINT.value, "exit_code": run["exit_code"],
                 "duration_s": run["duration_s"], "worktree": run["worktree"], "branch": run["branch"],
                 "turns": run["turns"], "session_id": run["session_id"], "pi_model": run["pi_model"],
                 "tokens": run["tokens"], "cost_usd": run["cost_usd"],
                 "cycle_time_s": int((now - datetime.fromisoformat(confirmed.replace("Z", "+00:00"))).total_seconds())
                 if confirmed else None}
        value = {k: v for k, v in value.items() if v is not None}
        records.append(journal.emit("task.executed", value, task_id,
                                    actor=actor or os.environ.get("TASKS_ACTOR", "pi")))
    return records


VERIFIER_RULES = """Você é um verificador independente: não fez este trabalho e não viu como foi feito. Confira a entrega \
contra o pedido confirmado, não contra o relato de quem a fez.

- Verifique a lacuna, não tudo: o que o relato diz que NÃO conseguiu checar, e o que só aparece fora dele (um app \
instalado, uma página no ar, o comportamento de verdade). Não rode de novo o que o relato já prova com evidência, \
a menos que você duvide dela.
- Rode o que prova (testes, build, o comando de verdade) dentro do worktree indicado; não edite nada.
- Se a entrega roda (um servidor, uma página, uma CLI), verifique-a rodando: suba numa porta de teste livre (nunca \
numa que já está em uso, que é de outra pessoa), chame o que mudou (a rota, a página, o comando), confira a resposta \
e derrube só o que você subiu. Testes unitários verdes provam as partes, não que elas ainda se encaixam.
- Cada checagem diz o que foi checado, como, a evidência que você viu (saída, trecho, número) e se passou.
- Termine com UM bloco JSON, o último da resposta, e nada depois dele:
```json
{"passed": true, "summary": "uma linha", "checks": [{"what": "...", "how": "...", "evidence": "...", "passed": true}]}
```
`passed` só é true quando todas as checagens passaram."""


def verifier_prompt(task_text: str, teach_back: str, delivery: dict) -> str:
    """The independent verifier's whole context: the request as explained, the repetition that was confirmed and the
    delivery under test (where it is and the executor's own report). Never the executor's transcript or learnings."""
    pr = delivery.get("pull_request") or {}
    where = [f"- worktree: {delivery.get('worktree') or '(não informado)'}",
             f"- branch: {delivery.get('branch') or '(não informado)'}"]
    if pr:
        where.append(f"- pull request: {pr.get('url', '')} (#{pr.get('number', '')})")
    return (VERIFIER_RULES + f"\n\n## O pedido, como foi explicado\n{task_text}\n\n"
            f"## O que foi entendido e confirmado por quem explicou\n{teach_back}\n\n"
            "## A entrega a verificar\n" + "\n".join(where) + "\n\n### Relato de quem fez\n"
            + (delivery.get("text") or "(sem relato)"))


def parse_verdict(answer: str) -> dict | None:
    """The last JSON object of the answer that has a "passed" key (a fenced block or bare), or None."""
    import re

    found, end = None, 0
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", answer):
        if m.start() < end:  # inside an object already read: the checks carry their own "passed"
            continue
        try:
            obj, end = decoder.raw_decode(answer, m.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "passed" in obj:
            found = obj
    return found


def verify(task_id: str, model: str | None = None, cwd: str | None = None, executed_id: str | None = None, *,
           actor: str | None = None) -> dict:
    """IV&V: pi in a fresh context checks a task.executed delivery against the confirmed request; records task.verified.

    The verifier sees only the task's text, the last confirmed teach-back and the delivery (worktree, branch, pull
    request and the executor's report). A verification that does not pass puts the task back where execute runs."""
    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state:
        raise ValueError(f"no task {task_id}")
    if state["status"] != "executed":
        raise ValueError(f"task {task_id} is {state['status']}: only an executed task is verified")
    history = journal.read({"id": task_id, "history": True})
    runs = [e for e in history if e["event"] == "task.executed"]
    target = next((e for e in runs if e["id"] == executed_id), None) if executed_id else runs[-1]
    if not target:
        raise ValueError(f"no task.executed {executed_id} on task {task_id}")
    spec = resolve_model(model or default_model())
    delivery = target["value"]
    work = Path(delivery.get("worktree") or "")
    where = work if delivery.get("worktree") and work.is_dir() else Path(cwd or os.getcwd()).resolve()
    run = _pi_exec(spec, verifier_prompt(state["text"], state["teach_backs"][-1], delivery), where,
                   delivery.get("branch", ""))
    verdict = parse_verdict(run["answer"])
    checks = [{"what": str(c.get("what", "")), "how": str(c.get("how", "")), "evidence": str(c.get("evidence", "")),
               "passed": c.get("passed") is True} for c in (verdict or {}).get("checks") or [] if isinstance(c, dict)]
    if verdict is None:
        checks = [{"what": "a resposta do verificador", "how": "último bloco JSON da resposta",
                   "evidence": "sem bloco JSON com `passed`: " + (run["answer"] or run["text"])[-300:], "passed": False}]
    if run["exit_code"] != 0:
        checks.append({"what": "a execução do verificador", "how": f"pi saiu com {run['exit_code']}",
                       "evidence": run["text"][-300:], "passed": False})
    passed = verdict is not None and verdict.get("passed") is True and run["exit_code"] == 0 \
        and all(c["passed"] for c in checks)
    ok = sum(c["passed"] for c in checks)
    summary = f"{'passou' if passed else 'não passou'}: {ok} de {len(checks)} checagens"
    if verdict and verdict.get("summary"):
        summary += f" — {verdict['summary']}"
    value = {"text": summary, "passed": passed, "checks": checks, "model": spec["id"], "provider": spec["provider"],
             "plan": spec["plan"], "duration_s": run["duration_s"], "exit_code": run["exit_code"],
             "executed_id": target["id"]}
    return journal.emit("task.verified", value, task_id, actor=actor or os.environ.get("TASKS_ACTOR", "pi"))


def deliver(task_id: str, kind: str, url: str | None = None, text: str | None = None, *,
            actor: str | None = None) -> dict:
    """Record task.delivered; only after a task.verified that passed. kind: pr, direct (a change made in place) or none."""
    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state:
        raise ValueError(f"no task {task_id}")
    if state["status"] != "verified":
        raise ValueError(f"task {task_id} is {state['status']}: only a task with a passing verification is delivered")
    if kind not in DELIVERY_KINDS:
        raise ValueError(f"kind is one of {list(DELIVERY_KINDS)}")
    value = {"text": text or {"pr": "entregue por pull request", "direct": "entregue direto, sem PR",
                              "none": "nada a entregar"}[kind], "kind": kind}
    if url:
        value["url"] = url
    return journal.emit("task.delivered", value, task_id, actor=actor)


def _pr_delivery(task_id: str, what: str) -> tuple[TasksJournal, dict]:
    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state:
        raise ValueError(f"no task {task_id}")
    if state["status"] != "delivered" or (state["delivery"] or {}).get("kind") != "pr":
        raise ValueError(f"task {task_id} is {state['status']}: {what} only follows a task.delivered with kind pr")
    return journal, state["delivery"]


def merge(task_id: str, url: str | None = None, *, actor: str | None = None) -> dict:
    """Record pull_request.merged (the agent ran `gh pr merge` itself); the url defaults to the delivery's."""
    journal, delivery = _pr_delivery(task_id, "a merge")
    value = {"text": "pull request merged"}
    if url or delivery.get("url"):
        value["url"] = url or delivery["url"]
    return journal.emit("pull_request.merged", value, task_id, actor=actor)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _gh() -> list[str]:
    return [os.environ.get("TASKS_GH", "gh")]


def _leftovers(repo: Path, branch: str) -> list[str]:
    """What of the task's workspace is still there, from the real git and gh: the worktree, the local branch, the remote
    branch, an open PR. Empty means clean. A tool that fails is a leftover too (unknown is not clean)."""
    left = []
    wl = _run(["git", "worktree", "list", "--porcelain"], repo)
    if wl.returncode != 0:
        left.append(f"git worktree list failed: {wl.stderr.strip()}")
    elif any(line == f"branch refs/heads/{branch}" for line in wl.stdout.splitlines()):
        left.append(f"worktree of {branch}")
    lb = _run(["git", "branch", "--list", branch], repo)
    if lb.returncode != 0 or lb.stdout.strip():
        left.append(f"local branch {branch}")
    rb = _run(["git", "ls-remote", "--heads", "origin", branch], repo)
    if rb.returncode != 0:
        left.append(f"git ls-remote failed: {rb.stderr.strip()}")
    elif rb.stdout.strip():
        left.append(f"remote branch origin/{branch}")
    op = _run([*_gh(), "pr", "list", "--head", branch, "--state", "open", "--json", "number"], repo)
    try:
        if op.returncode != 0:
            raise ValueError(op.stderr.strip())
        if json.loads(op.stdout or "[]"):
            left.append(f"open PR of {branch}")
    except ValueError as err:
        left.append(f"gh pr list failed: {err}")
    return left


def _pr_branch(repo: Path, url: str) -> str:
    done = _run([*_gh(), "pr", "view", url, "--json", "headRefName"], repo)
    try:
        return json.loads(done.stdout)["headRefName"] if done.returncode == 0 else ""
    except (ValueError, KeyError):
        return ""


def clean(task_id: str, repo: str | None = None, branch: str | None = None, *, actor: str | None = None) -> dict:
    """After pull_request.merged: make the workspace really clean, then record workspace.cleaned. The worktree goes
    through `wt remove` (never forced: it deletes the branch only when its content is in main), the remote branch is
    deleted only when its PR merged; then the checks run again from scratch and nothing is recorded if one fails."""
    journal = TasksJournal()
    state = journal.read({"id": task_id})
    if not state:
        raise ValueError(f"no task {task_id}")
    if state["status"] != "merged":
        raise ValueError(f"task {task_id} is {state['status']}: a workspace is cleaned only after pull_request.merged")
    root = Path(repo or os.getcwd()).expanduser().resolve()
    pr_url = (state.get("delivery") or {}).get("url", "")
    history = journal.read({"id": task_id, "history": True})
    x, _ = outcome_of(history)
    branch = branch or (_pr_branch(root, pr_url) if pr_url else "") or (x.branch if x else "")
    if not branch:
        raise ValueError(f"task {task_id}: no branch known (the PR names none and the run recorded none): pass --branch")
    wt = ""
    wl = _run(["git", "worktree", "list", "--porcelain"], root)
    block: dict[str, str] = {}
    for line in wl.stdout.splitlines() + [""]:
        if not line:
            if block.get("branch") == f"refs/heads/{branch}":
                wt = block.get("worktree", "")
            block = {}
        else:
            k, _, v = line.partition(" ")
            block[k] = v
    if wt and Path(wt).resolve() != root:
        done = _run([os.environ.get("TASKS_WT", "wt"), "remove", branch, "--foreground"], root)
        if done.returncode != 0:
            raise ValueError(f"wt remove {branch} refused: {(done.stderr or done.stdout).strip()}")
    elif _run(["git", "branch", "--list", branch], root).stdout.strip():
        done = _run(["git", "branch", "-d", branch], root)  # -d, never -D: git refuses an unmerged branch
        if done.returncode != 0:
            # a squash merge leaves the branch "unmerged" for git; wt knows the content is in main
            done = _run([os.environ.get("TASKS_WT", "wt"), "remove", branch, "--foreground"], root)
        if done.returncode != 0:
            raise ValueError(f"local branch {branch} is not merged: {(done.stderr or done.stdout).strip()}")
    merged = _run([*_gh(), "pr", "list", "--head", branch, "--state", "merged", "--json", "number"], root)
    remote = _run(["git", "ls-remote", "--heads", "origin", branch], root).stdout.strip()
    if remote:
        if merged.returncode != 0 or not json.loads(merged.stdout or "[]"):
            raise ValueError(f"remote branch origin/{branch} has no merged PR: it may hold unmerged work, not deleted")
        push = os.environ.get("TASKS_PUSH", "git push").split()
        done = _run([*push, "origin", "--delete", branch], root)
        if done.returncode != 0:
            raise ValueError(f"deleting origin/{branch} failed: {(done.stderr or done.stdout).strip()}")
    left = _leftovers(root, branch)
    if left:
        raise ValueError("not clean yet: " + "; ".join(left))
    return journal.emit("workspace.cleaned", {"text": "worktree, branch and PR gone", "branch": branch, "worktree": wt,
                                              "pr_url": pr_url, "repo": str(root)}, task_id, actor=actor)


def request_review(task_id: str, text: str, *, actor: str | None = None) -> dict:
    """Record pull_request.review_requested with the reason; the task goes back where execute runs."""
    journal, _ = _pr_delivery(task_id, "a review request")
    return journal.emit("pull_request.review_requested", {"text": text}, task_id, actor=actor)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="tasks: emit or read the global journal")
    sub = cli.add_subparsers(dest="cmd", required=True)
    em = sub.add_parser("emit")
    em.add_argument("event")
    em.add_argument("value", help="a JSON object")
    em.add_argument("--task")
    em.add_argument("--actor")
    ex = sub.add_parser("execute", help="run pi on a confirmed task, one model per worktree, in parallel")
    ex.add_argument("--task", required=True)
    ex.add_argument("--models", help="comma-separated ids of the registry (default: the recommended model)")
    ex.add_argument("--cwd")
    ex.add_argument("--actor")
    vf = sub.add_parser("verify", help="IV&V: pi in a fresh context checks an executed task's delivery")
    vf.add_argument("--task", required=True)
    vf.add_argument("--model", help="the verifier's registry id (default: the recommended model)")
    vf.add_argument("--cwd", help="where to run when the run recorded no worktree")
    vf.add_argument("--executed", help="the task.executed event to verify (default: the last one)")
    vf.add_argument("--actor")
    dl = sub.add_parser("deliver", help="task.delivered, after a passing verification")
    dl.add_argument("--task", required=True)
    dl.add_argument("--kind", required=True, choices=DELIVERY_KINDS)
    dl.add_argument("--url")
    dl.add_argument("--text")
    dl.add_argument("--actor")
    mg = sub.add_parser("merge", help="record pull_request.merged (run gh pr merge yourself first)")
    mg.add_argument("--task", required=True)
    mg.add_argument("--url")
    mg.add_argument("--actor")
    cl = sub.add_parser("clean", help="after the merge: verify and remove the worktree, branch and PR leftovers, then record")
    cl.add_argument("--task", required=True)
    cl.add_argument("--repo", help="the local clone to clean (default: the current directory)")
    cl.add_argument("--branch", help="when neither the PR nor the run names it")
    cl.add_argument("--actor")
    bn = sub.add_parser("branch", help="the branch name task/<id8>-<slug>")
    bn.add_argument("--task", required=True)
    bn.add_argument("--slug", required=True)
    rr = sub.add_parser("request-review", help="pull_request.review_requested: back to execution")
    rr.add_argument("--task", required=True)
    rr.add_argument("--text", required=True)
    rr.add_argument("--actor")
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
    sub.add_parser("models", help="the model registry, and which ones pi sees right now")
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
    elif args.cmd == "models":
        out(models_overview())
    elif args.cmd == "execute":
        ids = [m.strip() for m in args.models.split(",")] if args.models else None
        print(json.dumps(execute(args.task, args.cwd, ids, actor=args.actor), ensure_ascii=False))
    elif args.cmd == "verify":
        out(verify(args.task, args.model, args.cwd, args.executed, actor=args.actor))
    elif args.cmd == "deliver":
        out(deliver(args.task, args.kind, args.url, args.text, actor=args.actor))
    elif args.cmd == "merge":
        out(merge(args.task, args.url, actor=args.actor))
        print(f"next: tasks.sh clean --task {args.task} [--repo <clone>]  (the task is done only after workspace.cleaned)",
              file=sys.stderr)
    elif args.cmd == "clean":
        out(clean(args.task, args.repo, args.branch, actor=args.actor))
    elif args.cmd == "branch":
        print(branch_name(args.task, args.slug))
    elif args.cmd == "request-review":
        out(request_review(args.task, args.text, actor=args.actor))
    elif args.cmd == "emit":
        print(json.dumps(journal.emit(args.event, json.loads(args.value), args.task, actor=args.actor), ensure_ascii=False))
    else:
        print(json.dumps(journal.read({"id": args.task} if args.task else {}), ensure_ascii=False, indent=2))
