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
    uv run --script tasks.py execute --task <task_id> [--cwd <folder>]   # only after understanding.confirmed
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_DIR = "~/.local/share/tasks"
CONFIG = Path(os.environ.get("TASKS_CONFIG", "~/.config/tasks/config.json")).expanduser()
# Who executes a confirmed task. Default: the claude-code skill's print mode, on the mukutu account, with Sonnet.
# Override in CONFIG ({"execute": {"command": [...], "env": {...}}}); {prompt} is replaced by the task's prompt.
DEFAULT_EXECUTOR = {
    "command": ["claude", "-p", "--model", "sonnet", "--permission-mode", "acceptEdits", "{prompt}"],
    "env": {"CLAUDE_CONFIG_DIR": "~/.claude-mukutu"},
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
    cmd = [prompt if part == "{prompt}" else part for part in run["command"]]
    done = subprocess.run(cmd, cwd=cwd or os.getcwd(), env=env, capture_output=True, text=True)
    answer = (done.stdout.strip() or done.stderr.strip() or "(sem resposta)")[-4000:]
    return journal.emit("task.executed", {"text": answer, "exit_code": done.returncode, "executor": run["command"][0]},
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
    rd = sub.add_parser("read")
    rd.add_argument("--task")
    args = cli.parse_args()
    journal = TasksJournal()
    if args.cmd == "execute":
        print(json.dumps(execute(args.task, args.cwd, actor=args.actor), ensure_ascii=False))
    elif args.cmd == "emit":
        print(json.dumps(journal.emit(args.event, json.loads(args.value), args.task, actor=args.actor), ensure_ascii=False))
    else:
        print(json.dumps(journal.read({"id": args.task} if args.task else {}), ensure_ascii=False, indent=2))
