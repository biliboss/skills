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
    # um card movido) ou nenhuma; o PR é um tipo de entrega, não um passo obrigatório (verify e deliver: rascunho, só
    # no grafo).
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
    # experimento, o merge direto; produto ou cliente, pedir a revisão antes (deixar aberto não é evento). Os nomes são
    # os do GitHub (rascunho: só no grafo).
    "pull_request": {"merge": "merged", "request_review": "review_requested"},
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
    "task.executed": ["task.verified"],
    "task.verified": ["task.delivered", "task.executed"],  # did not pass: executed again (another executor or by hand)
    # A delivered PR: the Human merges it or asks for a review (an INITIAL edge would hide a whole category from the
    # derived graph, so the decision hangs off task.delivered); a review goes back to execution.
    "task.delivered": ["pull_request.merged", "pull_request.review_requested"],
    "pull_request.review_requested": ["task.executed"],
}


MEDIA_DIR = Path(os.environ.get("TASKS_DIR", DEFAULT_DIR)).expanduser() / "media"  # pictures of executed tasks


def result_from(value: dict) -> ExecutionResult | None:
    """The ExecutionResult a task.executed value carries, or None when the run recorded only its text (older runs)."""
    full = {"method", "harness", "model", "effort", "cycle_time_s", "delivery"} <= value.keys()
    pi = {"exit_code", "worktree"} <= value.keys()  # a pi run (0.11.0), one per model
    if not full and not pi:
        return None
    pic = lambda p: Picture(p["src"], p.get("caption", ""))  # noqa: E731
    pr = value.get("pull_request")
    s = value.get("session") or {}

    def one_of(enum, key):  # a field older runs always carried; a pi run may not have it
        return enum(value[key]) if key in value else None

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
        session=SessionRef(Harness(s.get("harness", value["harness"])), s.get("id"), s.get("log", "")) if full else None,
        pull_request=PullRequest(pr["number"], pr["url"], PullRequestState(pr["state"])) if pr else None,
        commits=tuple(Commit(c["sha"], c["message"], c["repo"]) for c in value.get("commits", [])),
        before_afters=tuple(BeforeAfter(b["title"], pic(b["before"]), pic(b["after"])) for b in value.get("before_afters", [])),
        journeys=tuple(Journey(j["title"], tuple(pic(x) for x in j["steps"])) for j in value.get("journeys", [])),
        provider=value.get("provider", ""), plan=value.get("plan", ""), exit_code=value.get("exit_code"),
        duration_s=value.get("duration_s"), worktree=value.get("worktree", ""), branch=value.get("branch", ""),
        turns=value.get("turns"), tokens=value.get("tokens"), cost_usd=value.get("cost_usd"),
    )


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


def _worktree_for(repo: Path, id8: str, mid: str) -> tuple[Path, str]:
    """The model's own git worktree, from the repo's HEAD: <repo>/../<repo>.task-<id8>-<model> on branch
    task/<id8>-<model> (reused when it already exists, so a re-run lands on the same branch)."""
    import subprocess

    path = repo.parent / f"{repo.name}.task-{id8}-{mid}"
    branch = f"task/{id8}-{mid}"
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
    import subprocess
    import time

    worktree, branch = _worktree_for(repo, id8, spec["id"])
    cmd = ["pi", "-p", "--no-session", "--mode", "json", "--model", spec["model"], prompt]
    started = time.monotonic()
    done = subprocess.run(cmd, cwd=worktree, env={**os.environ, **_model_env(spec)}, capture_output=True, text=True)
    run = {"worktree": str(worktree), "branch": branch, "exit_code": done.returncode,
           "duration_s": int(time.monotonic() - started), "turns": 0, "session_id": None, "pi_model": None,
           "tokens": None, "cost_usd": None, "text": ""}
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
    prompt = (f"Tarefa: {state['title']}\n\nComo foi explicada:\n{state['text']}\n\n"
              f"Como foi entendida (confirmado por quem explicou):\n{state['teach_backs'][-1]}\n\n"
              + ("Ajustes de quem explicou:\n" + "\n".join(f"- {x}" for x in state["learnings"]) + "\n\n" if state["learnings"] else "")
              + "Execute a tarefa e termine com um relato curto do que fez.")
    repo, id8 = Path(cwd or os.getcwd()).resolve(), task_id[:8]
    with ThreadPoolExecutor(max_workers=len(specs)) as pool:  # "does it work on this model?": one worktree each
        runs = list(pool.map(lambda spec: _pi_run(spec, prompt, repo, id8), specs))
    history = journal.read({"id": task_id, "history": True})
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
    elif args.cmd == "emit":
        print(json.dumps(journal.emit(args.event, json.loads(args.value), args.task, actor=args.actor), ensure_ascii=False))
    else:
        print(json.dumps(journal.read({"id": args.task} if args.task else {}), ensure_ascii=False, indent=2))
