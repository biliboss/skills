"""Tasks: someone explains a task, and at the end the one who received it repeats it back as they understood it.

The practice is teach-back ("explain it back in your own words", from health literacy) and the loop it closes is
closed-loop communication (aviation, crew resource management). Task is the most universal name for a piece of work
given to someone: a to-do at home, an assignment at school, a ticket in a software team.

Design stage: two events, a JSONL journal next to this file that may be edited by hand.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    """The journal is a JSONL file next to this one (design stage: edit it by hand)."""

    def __init__(self) -> None:
        self.path = Path(__file__).with_name("tasks.jsonl")

    def read(self, query: dict | None = None) -> Any:
        """{} -> every Task; {"id"} -> one; {"id", "history"} -> its events; {"event"} -> that type; {"history"} -> all."""
        query = query or {}
        events = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
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
