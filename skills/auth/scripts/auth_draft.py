"""Biliboss Skills - Auth: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Provider(AggregateRoot):
    """Provider: the aggregate root of Biliboss Skills - Auth."""

    accounts: list[Account]

    def update(self) -> ProviderUpdated: ...


class Account(Entity):
    """Account: held by Provider."""

    def update(self) -> AccountUpdated: ...
    def connect(self) -> AccountConnected: ...
    def check(self) -> AccountChecked: ...
    def disconnect(self) -> AccountDisconnected: ...
