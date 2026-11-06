"""Tournament in the dev-console: rounds of 4 options until the owner accepts the champion."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tournament import INITIAL, TRANSITIONS, TournamentJournal  # noqa: E402,F401

NAME = "Biliboss Skills - Choice"
SLUG = "choice"
SOURCE = Path(__file__).parent / "tournament.py"  # the file with EVENTS
ENTITY = "Tournament"
ENTITY_PLURAL = "torneios"
ENTITIES = {"tournament": "Tournament", "round": "Round"}
ENTITY_KEY = "tournament"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = TournamentJournal()


def title_of(history: list[dict], state: dict) -> str:
    return state.get("theme") or state.get("id", "")
