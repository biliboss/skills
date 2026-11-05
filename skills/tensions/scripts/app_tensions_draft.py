"""Tensions: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Tension(AggregateRoot):
    """Tension: the aggregate root of Tensions."""

    id: Any
    actual: Any
    desired: Any
    context: Any
    status: Any
    created_at: Any
    updated_at: Any
    event_count: Any
    observations: list[Observation]
    relationships: list[Relationship]
    actions: list[Action]

    def create(self) -> ManagementCreated: ...
    def update(self) -> ManagementUpdated: ...


class Observation(Entity):
    """Observation: held by Tension."""

    def record(self) -> ObservationRecorded: ...


class Relationship(Entity):
    """Relationship: held by Tension."""

    def link(self) -> RelationshipLinked: ...
    def unlink(self) -> RelationshipUnlinked: ...


class Action(Entity):
    """Action: held by Tension."""

    def propose(self) -> ActionProposed: ...
    def start(self) -> ActionStarted: ...
    def complete(self) -> ActionCompleted: ...
