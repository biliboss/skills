# /// script
# requires-python = ">=3.11"
# ///
"""The Input of the tasks skill: everything that reaches the agent when someone explains a task.

This file is the contract. Each class is a value object (frozen dataclass: equal by its values, no identity of its
own); the dev-console reads this file with `ast` and draws it as a graph, so the classes, their docstrings and
their fields are the only source. A class marked `assembled_by_harness` is put together by the harness (Claude
Code, Hermes, pi), and most of it the person who explains the task never sees.

Check a recorded input:  uv run --script input.py check <input.json>
"""
from __future__ import annotations

import json
import sys
from dataclasses import MISSING, dataclass, fields
from typing import ClassVar, get_type_hints


@dataclass(frozen=True)
class UserPrompt:
    """The explanation itself, in the words of whoever gave it."""

    text: str
    author: str


@dataclass(frozen=True)
class Skill:
    """The SKILL.md: its description picks the skill, its body says what to do."""

    name: str
    description: str
    body: str


@dataclass(frozen=True)
class SystemPrompt:
    """The harness's own instructions."""

    text: str


@dataclass(frozen=True)
class History:
    """The earlier messages of the session, or their summary after compaction."""

    messages: list[str]
    summary: str | None = None


@dataclass(frozen=True)
class Memory:
    """Facts kept between sessions."""

    facts: list[str]


@dataclass(frozen=True)
class Environment:
    """Date, folder and operating system."""

    date: str
    cwd: str
    platform: str


@dataclass(frozen=True)
class Tools:
    """What the agent is allowed to call."""

    names: list[str]


@dataclass(frozen=True)
class SessionContext:
    """What the harness assembles around the prompt; most of it the person never sees."""

    assembled_by_harness: ClassVar[bool] = True

    system_prompt: SystemPrompt
    history: History
    memory: Memory
    environment: Environment
    tools: Tools


@dataclass(frozen=True)
class Input:
    """Everything that reaches the agent when someone explains a task."""

    user_prompt: UserPrompt
    skill: Skill
    session_context: SessionContext


def check(value: dict, cls: type = Input, path: str = "input") -> list[str]:
    """The problems of a recorded input against the contract: missing fields and nested objects that are not
    objects. Empty means it conforms."""
    problems: list[str] = []
    if not isinstance(value, dict):
        return [f"{path}: expected an object"]
    hints = get_type_hints(cls)
    for f in fields(cls):
        where = f"{path}.{f.name}"
        if f.name not in value:
            if f.default is MISSING and f.default_factory is MISSING:
                problems.append(f"{where}: missing")
            continue
        kind = hints[f.name]
        if isinstance(kind, type) and hasattr(kind, "__dataclass_fields__"):
            problems += check(value[f.name], kind, where)
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        sys.exit("usage: input.py check <input.json>")
    found = check(json.loads(open(sys.argv[2], encoding="utf-8").read()))
    print("\n".join(found) or "ok: the input conforms")
    sys.exit(1 if found else 0)
