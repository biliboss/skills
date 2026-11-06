"""Biliboss Skills - Brainstorm: domain draft. Dummy code, no implementation: edit it, the dev-console Domain tab redraws.

Base class = DDD stereotype (Evans, 2003). A field typed with another class is a relation.
"""
from __future__ import annotations

from typing import Any


class AggregateRoot: ...


class Entity: ...


class ValueObject: ...


class DomainEvent: ...


class Session(AggregateRoot):
    """Session: the aggregate root of Biliboss Skills - Brainstorm."""

    id: Any
    idea: Any
    cynefin: Any
    chosen: Any
    variables: list[Variable]
    links: list[Link]
    loops: list[Loop]
    status: Any
    updated_at: Any
    problems: list[Problem]
    questions: list[Question]
    approachs: list[Approach]
    leverages: list[Leverage]

    def start(self) -> SessionStarted: ...
    def finish(self) -> SessionFinished: ...


class Problem(Entity):
    """Problem: held by Session."""

    def classify(self) -> ProblemClassified: ...


class Question(Entity):
    """Question: held by Session."""

    def ask(self) -> QuestionAsked: ...
    def answer(self) -> QuestionAnswered: ...


class Variable(Entity):
    """Variable: held by Session."""

    def add(self) -> VariableAdded: ...


class Link(Entity):
    """Link: held by Session."""

    def add(self) -> LinkAdded: ...


class Loop(Entity):
    """Loop: held by Session."""

    def identify(self) -> LoopIdentified: ...


class Approach(Entity):
    """Approach: held by Session."""

    def propose(self) -> ApproachProposed: ...
    def choose(self) -> ApproachChosen: ...


class Leverage(Entity):
    """Leverage: held by Session."""

    def rank(self) -> LeverageRanked: ...
