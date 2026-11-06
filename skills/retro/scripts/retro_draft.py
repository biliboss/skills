"""Biliboss Skills - Retro: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Retro(AggregateRoot):
    """Retro: the aggregate root of Biliboss Skills - Retro."""

    id: Any
    skill: Any
    rule: Any
    status: Any
    recurred: Any
    updated_at: Any
    lessons: list[Lesson]

    def start(self) -> RetroStarted: ...


class Lesson(Entity):
    """Lesson: held by Retro."""

    def propose(self) -> LessonProposed: ...
    def accept(self) -> LessonAccepted: ...
    def reject(self) -> LessonRejected: ...
    def apply(self) -> LessonApplied: ...
    def recur(self) -> LessonRecurred: ...
