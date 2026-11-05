"""Tasks: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Task(AggregateRoot):
    """Task: the aggregate root of Tasks."""

    id: Any
    title: Any
    text: Any
    teach_backs: Any
    status: Any
    updated_at: Any
    understandings: list[Understanding]

    def explain(self) -> TaskExplained: ...


class Understanding(Entity):
    """Understanding: held by Task."""

    def teach_back(self) -> UnderstandingTaughtBack: ...
