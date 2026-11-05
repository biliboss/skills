"""dev-console: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Domain(AggregateRoot):
    """Domain: the aggregate root of dev-console."""

    id: Any
    slug: Any
    name: Any
    entity: Any
    source: Any
    home: Any
    widgets: list[Widget]
    actions: list[Action]
    status: Any
    event_count: Any
    updated_at: Any

    def design(self) -> DomainDesigned: ...
    def import(self) -> DomainImported: ...
    def draft(self) -> DomainDrafted: ...
    def set_home(self) -> DomainHomeSet: ...


class Widget(Entity):
    """Widget: held by Domain."""

    def design_widget(self) -> WidgetDesigned: ...
    def approve(self) -> WidgetApproved: ...
    def connect(self) -> WidgetConnected: ...


class Action(Entity):
    """Action: held by Domain."""

    def propose(self) -> ActionProposed: ...
    def simulate(self) -> ActionSimulated: ...
    def run(self) -> ActionRan: ...
