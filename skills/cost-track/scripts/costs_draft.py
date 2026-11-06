"""Biliboss Skills - Costs: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Worth(AggregateRoot):
    """Worth: the aggregate root of Biliboss Skills - Costs."""

    id: Any
    name: Any
    kind: Any
    budget_day: Any
    seconds: Any
    cost: Any
    updated_at: Any
    cost_centers: list[CostCenter]
    time_entrys: list[TimeEntry]

    def update(self) -> WorthUpdated: ...


class CostCenter(Entity):
    """CostCenter: held by Worth."""

    def update(self) -> CostCenterUpdated: ...


class TimeEntry(Entity):
    """TimeEntry: held by Worth."""

    def start(self) -> TimeEntryStarted: ...
    def stop(self) -> TimeEntryStopped: ...
