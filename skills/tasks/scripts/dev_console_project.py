"""Tasks in the dev-console: a task is explained, and the receiver teaches it back."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tasks import TasksJournal  # noqa: E402

NAME = "Tasks"
SLUG = "tasks"
SOURCE = Path(__file__).parent / "tasks.py"  # the file with EVENTS
ENTITY = "Task"
ENTITY_PLURAL = "tarefas"
ENTITIES = {"task": "Task", "understanding": "Understanding"}
ENTITY_KEY = "task_id"
PROJECTOR = "_project"

journal = TasksJournal()


def title_of(history: list[dict], state: dict) -> str:
    return state.get("title", "")


WIDGETS: dict = {}
