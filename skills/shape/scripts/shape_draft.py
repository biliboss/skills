"""Biliboss Skills - Shape: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Request(AggregateRoot):
    """Request: the aggregate root of Biliboss Skills - Shape."""

    pieces: list[Piece]
    understandings: list[Understanding]
    works: list[Work]

    def receive(self) -> RequestReceived: ...


class Piece(Entity):
    """Piece: held by Request."""

    def route(self) -> PieceRouted: ...


class Understanding(Entity):
    """Understanding: held by Request."""

    def teach_back(self) -> UnderstandingTaughtBack: ...
    def confirm(self) -> UnderstandingConfirmed: ...


class Work(Entity):
    """Work: held by Request."""

    def delegate(self) -> WorkDelegated: ...
