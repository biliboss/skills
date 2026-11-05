---
name: tensions
description: >-
  Record, retrieve and understand meaningful Tension events shared by agents.
  Use when a gap between actual and desired reality emerges, when evidence
  changes, when a decision needs a reason, or when an agent needs to read
  the evolution of a Tension. Not a task manager or agent runtime.
metadata:
  version: 0.1.0
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

- **management:** `created`, `redefined`, `resolved`, `reopened`, `archived`.
  Values: Definition, Resolution, Reason.
- **observation:** `recorded`, `corrected`, `disputed`.
  Values: Observation, Evidence, Reason.
- **reasoning:** `hypothesis_proposed`, `assessment_recorded`, `challenged`.
  Values: Hypothesis, Assessment.
- **relationship:** `linked`, `unlinked`, `decomposed`.
  Value: Relationship.
- **action:** `proposed`, `started`, `completed`, `failed`.
  Values: Proposal, Outcome.

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
    {"observation": "Traces found", "source": "HyperDX"},
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
