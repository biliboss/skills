"""Biliboss Skills - Review: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Review(AggregateRoot):
    """Review: the aggregate root of Biliboss Skills - Review."""

    id: Any
    file: Any
    line: Any
    severity: Any
    text: Any
    status: Any
    updated_at: Any
    findings: list[Finding]

    def start(self) -> ReviewStarted: ...
    def finish(self) -> ReviewFinished: ...


class Finding(Entity):
    """Finding: held by Review."""

    def report(self) -> FindingReported: ...
    def fix(self) -> FindingFixed: ...
    def dismiss(self) -> FindingDismissed: ...
