# /// script
# requires-python = ">=3.11"
# dependencies = ["sqlmodel>=0.0.22"]
# ///
"""The domain-model schema as SQLModel: the source of truth for the dm_* tables in the dev-console SQLite.

uv run models.py            -> create the dm_* tables (DM_DB overrides the path)
"""
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from sqlmodel import Field, SQLModel, create_engine

DB = Path(os.environ.get("DM_DB") or Path.home() / ".local/share/dev-console/dev-console.sqlite")


class Status(str, Enum):
    draft = "draft"
    real = "real"


class EntityKind(str, Enum):
    aggregate = "aggregate"
    entity = "entity"
    value = "value"


class Cardinality(str, Enum):
    one_one = "1:1"
    one_many = "1:N"
    many_one = "N:1"
    many_many = "N:N"


class Domain(SQLModel, table=True):
    __tablename__ = "dm_domain"
    slug: str = Field(primary_key=True)
    name: str
    purpose: Optional[str] = None
    status: Status = Field(default=Status.draft, sa_column_kwargs={"server_default": "draft"})


class Entity(SQLModel, table=True):
    __tablename__ = "dm_entity"
    domain: str = Field(primary_key=True, foreign_key="dm_domain.slug")
    name: str = Field(primary_key=True)
    kind: EntityKind = Field(default=EntityKind.entity, sa_column_kwargs={"server_default": "entity"})
    definition: Optional[str] = None
    status: Status = Field(default=Status.draft, sa_column_kwargs={"server_default": "draft"})


class Attribute(SQLModel, table=True):
    __tablename__ = "dm_attribute"
    domain: str = Field(primary_key=True, foreign_key="dm_domain.slug")
    entity: str = Field(primary_key=True)
    name: str = Field(primary_key=True)
    type: Optional[str] = None
    required: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})
    note: Optional[str] = None


class Relation(SQLModel, table=True):
    __tablename__ = "dm_relation"
    domain: str = Field(primary_key=True, foreign_key="dm_domain.slug")
    src: str = Field(primary_key=True)
    verb: str = Field(primary_key=True)
    dst: str = Field(primary_key=True)
    cardinality: Optional[str] = None  # one of Cardinality's values (1:1, 1:N, N:1, N:N)


class Command(SQLModel, table=True):
    __tablename__ = "dm_command"
    domain: str = Field(primary_key=True, foreign_key="dm_domain.slug")
    name: str = Field(primary_key=True)
    entity: str
    actor: Optional[str] = None
    emits: Optional[str] = None
    status: Status = Field(default=Status.draft, sa_column_kwargs={"server_default": "draft"})


class Event(SQLModel, table=True):
    __tablename__ = "dm_event"
    domain: str = Field(primary_key=True, foreign_key="dm_domain.slug")
    name: str = Field(primary_key=True)  # category.event
    entity: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    status: Status = Field(default=Status.draft, sa_column_kwargs={"server_default": "draft"})


class Term(SQLModel, table=True):
    __tablename__ = "dm_term"
    domain: str = Field(primary_key=True, foreign_key="dm_domain.slug")
    term: str = Field(primary_key=True)
    definition: str
    avoid: Optional[str] = None


# --- Phases: one table per phase, numbered so they sort in order in any SQLite viewer ---

class OverviewDiagram(SQLModel, table=True):
    """Phase 01: the overview diagrams, one per type (domain, architecture...). At most 9 nodes per diagram; an edge
    row joins two of them."""
    __tablename__ = "01_overview_diagram"
    domain: str = Field(primary_key=True, foreign_key="dm_domain.slug")
    diagram: str = Field(primary_key=True, sa_column_kwargs={"server_default": "domain"})  # domain | architecture
    pos: int = Field(primary_key=True)          # reading order; nodes 1-9 first, then edges
    row: str = Field(sa_column_kwargs={"server_default": "node"})  # node | edge
    item: str                                   # node name, or the edge's source node
    kind: Optional[str] = None                  # domain: aggregate|entity|value; architecture: actor|ui|service|code|store
    verb: Optional[str] = None                  # edge: the label
    target: Optional[str] = None                # edge: the destination node
    cardinality: Optional[str] = None           # edge: 1:1 | 1:N | N:1 | N:N
    note: Optional[str] = None                  # node: one line that explains it
    status: Status = Field(default=Status.draft, sa_column_kwargs={"server_default": "draft"})


def engine():
    return create_engine(f"sqlite:///{DB}")


if __name__ == "__main__":
    SQLModel.metadata.create_all(engine())
    print(f"ok: dm_* tables in {DB}")
