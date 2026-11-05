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

EVENTS = {
    # Alguém explicou uma tarefa a outra pessoa, do jeito dele e com o tempo que ela pedia.
    "task": {"explain": "explained"},
    # No fim, quem recebeu a tarefa repetiu tudo o que ouviu, do jeito que entendeu (o teach-back).
    "understanding": {"teach_back": "taught_back"},
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
                # explained or taught_back
                "status": "explained",
                # when the task last moved
                "updated_at": e["at"],
            }
        if state is None:
            continue
        if event == "understanding.taught_back":
            state["teach_backs"].append(value["text"])
            state["status"] = "taught_back"
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


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="tasks: emit or read the global journal")
    sub = cli.add_subparsers(dest="cmd", required=True)
    em = sub.add_parser("emit")
    em.add_argument("event")
    em.add_argument("value", help="a JSON object")
    em.add_argument("--task")
    em.add_argument("--actor")
    rd = sub.add_parser("read")
    rd.add_argument("--task")
    args = cli.parse_args()
    journal = TasksJournal()
    if args.cmd == "emit":
        print(json.dumps(journal.emit(args.event, json.loads(args.value), args.task, actor=args.actor), ensure_ascii=False))
    else:
        print(json.dumps(journal.read({"id": args.task} if args.task else {}), ensure_ascii=False, indent=2))
