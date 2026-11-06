"""Retro in the dev-console: the owner's corrections become rules in the skills (design stage)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from retro import TRANSITIONS, RetroJournal  # noqa: E402,F401

NAME = "Biliboss Skills - Retro"
SLUG = "retro"
SOURCE = Path(__file__).parent / "retro.py"  # the file with EVENTS
ENTITY = "Lesson"
ENTITY_PLURAL = "lições"
ENTITIES = {"retro": "Retro", "lesson": "Lesson"}
ENTITY_KEY = "lesson"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = RetroJournal()

# The owner starts a retro.
INITIAL = ["retro.started"]


def title_of(history: list[dict], state: dict) -> str:
    return state.get("rule") or state.get("id", "")
