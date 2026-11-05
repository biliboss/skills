"""Tensions: a tiny, dependency-free shared domain event journal.

Storage: ~/.local/share/tensions/events.jsonl (override TENSIONS_DIR).
One JSON object per line; POSIX flock protects concurrent writers/readers.
No server, MCP, agent framework or NATS required.
"""
from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_DIR = Path.home() / ".local" / "share" / "tensions"
# Command -> event it records, per category, in the order a Tension lives them.
# The first management command creates the Tension; every other category opens from it.
EVENTS = {
    "management": {"create": "created", "update": "updated"},
    "observation": {"record": "recorded"},  # a new Recorded may supersede 0..N earlier ones by its value
    "relationship": {"link": "linked", "unlink": "unlinked"},
    "action": {"propose": "proposed", "start": "started", "complete": "completed"},
}
AUDIENCES = {"human", "agent"}
# Lines written by v0.1 stay readable: their old names project like the current ones.
LEGACY = {"management.redefined": "management.updated"}


class Tensions:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory or os.environ.get("TENSIONS_DIR", DEFAULT_DIR)).expanduser()
        self.path = self.directory / "events.jsonl"

    def emit(
        self,
        event: str,
        value: Any,
        tension_id: str | None = None,
        *,
        actor: str | None = None,
    ) -> dict:
        """Append a meaningful event. Creation generates tension_id if absent."""
        category, separator, verb = event.partition(".")
        if not separator or verb not in EVENTS.get(category, {}).values():
            raise ValueError(f"Unknown event: {event}")
        if not isinstance(value, dict) or not value:
            raise ValueError("Value must be a non-empty JSON object")
        # Who an Observation is written for: "human" (a plain sentence a person reads in the console)
        # or "agent" (a fact for machines: ids, states, raw numbers). Absent means "agent".
        if category == "observation" and value.get("audience", "agent") not in AUDIENCES:
            raise ValueError(f"Observation audience must be one of {sorted(AUDIENCES)}")
        if category == "management" and verb == "created":
            tension_id = tension_id or str(uuid4())
            if not {"actual", "desired"} <= value.keys():
                raise ValueError("Created Definition needs actual and desired")
        elif not tension_id:
            raise ValueError("tension_id is required except for management.created")

        record = {
            "id": str(uuid4()),
            "tension_id": tension_id,
            "event": event,
            "actor": actor or os.environ.get("TENSIONS_ACTOR", "unknown"),
            "value": value,
            "at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        }
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            # A private journal by default; existing files retain their permissions.
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            os.close(fd)
        with self.path.open("ab", buffering=0) as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            try:
                file.write(encoded)
                os.fsync(file.fileno())
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)
        return record

    def read(self, query: dict | None = None) -> Any:
        """Read events, one Tension projection, or a list of projections.

        {"id": "..."} -> projection
        {"id": "...", "history": True} -> chronological events
        {"event": "observation.recorded"} -> matching event records
        {} -> current projections for every Tension
        """
        query = query or {}
        if not isinstance(query, dict):
            raise TypeError("query must be a dict")
        events = self._events()
        if "id" in query:
            matches = [e for e in events if e["tension_id"] == query["id"]]
            return matches if query.get("history") else self._project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for event in events:
            groups.setdefault(event["tension_id"], []).append(event)
        return [state for group in groups.values() if (state := self._project(group))]

    def _events(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("rb") as file:
                fcntl.flock(file, fcntl.LOCK_SH)
                try:
                    records = file.read().splitlines()
                finally:
                    fcntl.flock(file, fcntl.LOCK_UN)
        except FileNotFoundError:
            return []
        return [json.loads(line) for line in records if line.strip()]

    @staticmethod
    def _project(events: list[dict]) -> dict | None:
        state = None
        for e in events:
            event, value = LEGACY.get(e["event"], e["event"]), e["value"]
            if event == "management.created":
                state = {
                    "id": e["tension_id"],
                    "actual": value["actual"],
                    "desired": value["desired"],
                    "context": value.get("context", {}),
                    "status": "open",
                    # Private and immutable: set once by management.created; no later event writes it.
                    "created_at": e["at"],
                    "updated_at": e["at"],
                    "event_count": 0,
                }
            if state is None:
                continue
            if event == "management.updated":
                for key in ("actual", "desired", "context"):
                    if key in value:
                        state[key] = value[key]
            # v0.1 lines only: no command records these any more.
            if event in ("management.resolved", "management.reopened", "management.archived"):
                state["status"] = "open" if event == "management.reopened" else event.split(".")[1]
            state["updated_at"] = e["at"]
            state["event_count"] += 1
        return state
