---
name: tensions
description: >-
  Record, retrieve and understand meaningful Tension events shared by agents.
  Use when a gap between actual and desired reality emerges, when evidence
  changes, when a decision needs a reason, or when an agent needs to read
  the evolution of a Tension. Not a task manager or agent runtime.
metadata:
  version: 0.2.0
---

# Tensions

**One Entity:** Tension (the perceived gap between actual and desired).
**One historical record:** append-only JSONL shared by local agents.
**Two operations:** `Tensions.read(query)` and `Tensions.emit(event, value, tension_id=None)`.

The Skill is in `biliboss/skills`; storage is global and outside repositories:
`~/.local/share/tensions/events.jsonl`. Override the directory with
`TENSIONS_DIR` (all agents must point to the same directory). This is
**machine-global**, not network-global: remote agents need a shared filesystem
or a future synchronization layer. Never commit the journal.

## When to record

Only emit events that preserve a meaningful domain Value Object. An Event
says what happened; its `value` holds an immutable snapshot of what mattered.
Don't record every tool call, log line, or transient agent thought.
Observations can be disputed or corrected: append new events; never edit history.

## Categories

The source of truth is `EVENTS` in `scripts/app_tensions.py`: per category, each
command and the event it records, in the order a Tension lives them.

- **management:** `create` → `created`, `update` → `updated`. Value: Definition.
- **observation:** `record` → `recorded`. Values: Observation, Evidence. A new
  Recorded may supersede 0..N earlier ones through its value.
  Each Observation says who it is written for: `audience` is `human` (a plain
  sentence a person reads in the console; clarity first, no times or ids inside) or
  `agent` (ids, states, raw numbers; the default). Record the human one when a
  person should read the fact.
- **relationship:** `link` → `linked`, `unlink` → `unlinked`. Value: Relationship.
- **action:** `propose` → `proposed`, `start` → `started`, `complete` → `completed`.
  Values: Proposal, Outcome. An Action starts as `proposed`; `started` and
  `completed` point back with `proposal_id`.

Lines written by v0.1 stay readable (`management.redefined` projects as `updated`).

A Value Object is reusable; no need to define a new VO class for each event.
The naming is deliberately semantic, not the name of an execution workflow.

## Use Python directly

`S` is the directory containing this skill. The script uses only Python
standard library (Python 3.10+ on macOS/Linux). `just` is optional convenience,
not a runtime dependency; recipes live in `scripts/justfile`.

```python
import sys
sys.path.insert(0, "/path/to/tensions/scripts")
from app_tensions import Tensions

app = Tensions()
created = app.emit(
    "management.created",
    {"actual": "MCP errors are invisible", "desired": "Errors are traceable"},
    actor="agent-a",
)
app.emit(
    "observation.recorded",
    {"value": "Traces found", "source": "HyperDX", "observed_at": "2026-11-04T20:00:00Z"},
    tension_id=created["tension_id"],
    actor="agent-b",
)
print(app.read({"id": created["tension_id"]}))
print(app.read({"id": created["tension_id"], "history": True}))
```

`emit` is synchronous and acknowledges a local append; `read` returns
projections or historical events. `scripts/justfile` gives agent-friendly
recipes: `just --justfile scripts/justfile list`,
`just --justfile scripts/justfile read <id>`, and
`just --justfile scripts/justfile emit <event> <json-file> [tension-id]`.
The last recipe reads the payload from a JSON file rather than passing raw JSON
through a shell command.

## Before shaping values or screens: read the model

The domain model is decided in the Linear project **Tensions** (project content =
the `Tension` class with one method per event; docs BRIEF.md, AGENTS.md,
ARCHITECTURE.md, "Tension Event Categories — Draft"; newest doc wins). Read them
(`lin.sh` of skill `linear`: `projects(filter:{name:{containsIgnoreCase:"tension"}})`
with `documents`, then `document(id){content}`) before naming a field, a Value
Object or a screen block — otherwise you invent names ("Fact") the model already
has (Observation). Notes for humans live in `~/biliboss/.wiki/skill-tensions-o-que-e.md`.

- Entity ≠ Value Object ≠ Event: a fact enters **as an event**
  (`observation.recorded`) with the Observation Value Object as its `value`; no
  new class or event type for it.
- Observation VO: `value`, `observed_at`, `source`, `audience` (`human`|`agent`, the
  core refuses anything else; absent = agent) (+ `evidence` list optional). The core
  validates only `audience`, so follow the rest by hand.
- **A fact a person should read gets its own `audience: human` observation**: one clear
  sentence, no time, id or count inside (those stay in `observed_at` and the agent
  record). Keep the agent observation as is; never rewrite history to make it readable.

## Value conventions (what the viewer reads)

- `management.created`: `title` (business result, one line), `actual`, `desired`,
  `context` {project, version, owner, source}.
- `relationship.linked`: `{kind, target, title}`; `target` is the work id (e.g. a
  Linear card). The linked item's state (card in Done, PR open) is something
  **observed**: `observation.recorded` {value, target, state, observed_at, source}.
  Never record it as an Action — work done before or outside this Tension is not
  its action.
- **Action = what is done because of this Tension, and it always starts as
  `action.proposed`** {proposal, target|targets}. `started`/`completed`/`failed`
  only follow a proposal of this Tension and carry `proposal_id` (the proposed
  event's `id`); `completed` carries `outcome`. A fresh Tension has no action
  but proposals.
- **A proposal for humans** carries `title` (one line, the result), `subtitle` (one
  sentence: what and why), `proposal` (the instruction an agent executes), `target`, and
  `expected` (what is delivered at the end, a dev-console spec: `{kind: report|list|table|
  widget, title, data}`). To improve an old proposal, emit a new `action.proposed` with
  `supersedes: [<old ids>]`; viewers hide the superseded ones (never edit the journal).
- **First proposal = look before acting**: survey what is actually open (for a
  repo: `gh pr list --state open` plus remote branches besides main with
  `gh api repos/<r>/compare/main...<b>` for ahead/behind/last commit, and which
  have no PR). Fix-it proposals (merge, ping an agent) come after, from that
  survey — proposing them first was rejected.
- **A new Tension records the proposal only.** Do not run it and append
  `started`/`completed` while seeding: a fresh Tension shows no Action besides
  `proposed`. Its findings become observations when the proposal is really
  executed later, with `proposal_id`.
- The journal is append-only and has no archive command: read the model and the
  rules above **before** seeding. When the model changes incompatibly, rotate the
  journal (`mv events.jsonl events.v<N>.jsonl` — never delete) and seed again;
  old lines stay readable through `LEGACY` in the core.
- When recording a fact that happened earlier, put the real time in
  `value.observed_at` (UTC ISO); `at` is only the append time.
- Write `value` of an Observation as one sentence a human reads about the world
  ("O receptor de eventos do Via já roda na agents-vps"), not a record dump
  ("DVM-278 está em Done"); the card id and its state go in `target` and `state`.
  An Observation has no status of its own: never add "holds the tension",
  "resolved" or groupings to it.
- Write seed/backfill payloads in a script file run with `uv run --script`, not
  inline JSON in the shell.
- `actual` and `desired` describe the **gap**, in plain colloquial PT-BR, one
  sentence each ("Tem trabalho começado e largado no meio…" × "Todo trabalho
  começado termina…"). Counts, card ids and PR numbers are **facts**: record
  each as its own `observation.recorded` {value, observed_at, source, evidence?} instead
  of packing them into `actual` — otherwise the definition goes stale with every
  new number and repeats the facts block.
- Gather facts from the real sources before writing them (Linear state from the
  mesa_focus KV, `gh pr list/view` for PRs); "we don't know X" is itself a fact
  worth an observation.
- To fix a Tension's wording, emit `management.updated` {actual?, desired?,
  reason} through the skill (`just … emit management.updated <json-file> <id>`,
  `TENSIONS_ACTOR` set) — never edit the journal or hardcode text in the view.

## View (optional, read-only)

The screen is the **`dev-console` skill** (one file, any project); this skill only
hooks into it with `scripts/dev_console_project.py`:
`uv run --script <dev-console>/scripts/dev-console.py --project scripts/dev_console_project.py`.
The console's UI rules live in that skill. What is Tensions-specific stays here, in
the project file: names (`Tension`, `tensões`, `tension_id`), `title_of`, and
`WIDGETS` — each event's views (`management.created` → TensionList +
TensionDetail, …). To show something new for an event, add a function to
`WIDGETS` there, never in the console. `references/tension-model.py` keeps the
Linear project's model text for reference only.

**The code is the source of the model.** Categories, commands, events and their
order live only in `EVENTS` (`{category: {command: event}}`); the view derives
the command list and the graph from it, live. To change the model (add, drop,
rename a command), edit `EVENTS` — never a table in the view — then update
"Categories" above and the CHANGELOG. Keep it minimal: Gabriel cuts what is not
used (no reasoning category, no `decomposed`, `failed`, `resolved`, `archived`,
`corrected`, `disputed`). Removing a category from `EVENTS` also removes its tab
and counter in the view.

**Naming:** commands are imperative (`create`, `update`, `record`, `propose`),
events are past tense, shown as `Entity.Event` (`Tension.Created`,
`Tension.Updated`).

**Projection fields:** `created_at` is private and immutable (set once by
`management.created`, no later event writes it); `updated_at` moves with every
event. A new projection field needs no migration: `read` replays the journal.

The project file imports FastHTML from the console's environment: never import it
from `app_tensions.py` nor add deps to the core.

## Boundaries and limitations

- No NATS, uv packages, CLI application, MCP or HTTP server in V0.1.
- This uses POSIX `flock` to coordinate local readers and writers. It is not
  safe to assume that network-mounted filesystems provide the same guarantees.
- Events are stored in append order, not globally ordered by actor timestamps.
- Avoid personal data, secrets and untrusted large payloads. JSONL is plaintext;
  protect permissions and retention at the filesystem level.
- `read` replays the entire journal (appropriate for V0.1); an index or
  projection can be introduced after demonstrating a performance need.
- The core file has no authorization, exactly-once delivery, or cross-host sync.
  Agents must not treat their local file as a shared log across different hosts.
