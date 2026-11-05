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
    events: list[Event]
    tabs: list[Tab]
    widgets: list[Widget]
    status: Any
    event_count: Any
    updated_at: Any

    def design(self) -> DomainDesigned: ...
    def import(self) -> DomainImported: ...
    def update(self) -> DomainUpdated: ...


class Event(Entity):
    """Event: held by Domain."""

    def update_event(self) -> EventUpdated: ...


class Widget(Entity):
    """Widget: held by Domain."""

    def update_widget(self) -> WidgetUpdated: ...


class Tab(Entity):
    """Tab: held by Domain."""

    def update_tab(self) -> TabUpdated: ...
