---
name: domain-model
description: >-
  Model a project's domain directly in the dev-console SQLite (~/.local/share/dev-console/dev-console.sqlite,
  dm_* tables mapped by SQLModel in scripts/models.py): domain, entities, attributes, relations, commands,
  events and glossary terms, each draft until the owner confirms it or the code proves it. The owner watches
  the rows appear in his SQLite viewer. Use when the user says "domain-model", "modela o domínio", "modela no
  sqlite", "desenha as entidades". Not domain-plan (events and screens vs code drift in the dev-console
  journal); this one is the static model.
metadata:
  version: 0.1.0
---

# domain-model

The model is rows, not a document: whatever is modeled shows on screen the moment it is written.

## Schema

`scripts/models.py` (SQLModel) is the source of truth: `Domain` (dm_domain), `Entity` (dm_entity, kind
aggregate|entity|value), `Attribute`, `Relation` (verb + cardinality 1:1|1:N|N:1|N:N), `Command` (actor, the
event it emits), `Event` (`category.event`, from_state → to_state), `Term` (the word, what to avoid). Status
is `draft` by default, in the database too (server defaults), so raw SQL inserts work. Change the schema in
`models.py` only, never with hand-written DDL. `DM_DB` points to another file.

## Steps

1. `uv run scripts/models.py` creates the missing `dm_*` tables. It never touches the console's `widgets`/`home`.
2. Draft the domain one table at a time so the owner watches it grow: the `dm_domain` row, then entities,
   attributes, relations, commands, events, terms. Write through SQLModel (`from models import *`, a
   `Session(engine())`) or `sqlite3` with `INSERT OR REPLACE`.
3. Take names from the code and the wiki and never invent them. Every row starts as `draft`.
4. Read it back (`sqlite3 -header -column <db> "select * from dm_entity where domain='<slug>'"`). When the owner
   confirms, set `status='real'`.

## Phases: one table per phase

Each phase is its own table, numbered (`01_`, `02_`...) so the viewer lists them in order, above the `dm_*` tables.
A diagram is many rows: one row per node, one row per edge, which is the fastest way to write it and to read it in
the viewer.

- `01_overview_diagram`: the one picture that explains the whole domain. **At most 9 nodes**
  (`row='node'`, `item`, `kind`, `note`, pos 1-9), then the edges (`row='edge'`, `item` → `target`, `verb`,
  `cardinality`, pos 10+). Write it first. Choose the 9 that let a newcomer understand everything: the aggregate
  root, the entities a command touches, and the events that change them.

Seed of this skill's own phase 01: `sqlite3 <db> < scripts/seed-01-overview.sql`.

## On screen (dev-console)

The dev-console's `console_model.py` module serves `/model/<slug>`. It reads `01_overview_diagram` (or, before the
phase exists, derives the map from `dm_entity` + `dm_relation`) and redraws the Mermaid diagram every 1.5 s, but only
when the rows changed. Draft is a dashed border, real a solid one. `/model` lists the domains.

The first model is this skill itself: `sqlite3 <db> < scripts/seed-self.sql` (domain `domain-model`).
