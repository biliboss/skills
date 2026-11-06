"""Biliboss Skills - Kanban: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Card(AggregateRoot):
    """Card: the aggregate root of Biliboss Skills - Kanban."""

    id: Any
    title: Any
    domain: Any
    stage: Any
    since: Any
    created_at: Any
    updated_at: Any

    def create(self) -> CardCreated: ...
    def move(self) -> CardMoved: ...
