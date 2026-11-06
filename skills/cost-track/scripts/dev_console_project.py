"""Costs in the dev-console: everything is monetary, everything has a cost (design stage)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from costs import TRANSITIONS, CostsJournal  # noqa: E402,F401

NAME = "Biliboss Skills - Costs"
SLUG = "costs"
SOURCE = Path(__file__).parent / "costs.py"  # the file with EVENTS
ENTITY = "CostCenter"
ENTITY_PLURAL = "centros de custo"
ENTITIES = {"worth": "Worth", "cost_center": "CostCenter", "time_entry": "TimeEntry"}
ENTITY_KEY = "cost_center"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = CostsJournal()

# The Human starts by saying what he is worth.
INITIAL = ["worth.updated"]


def title_of(history: list[dict], state: dict) -> str:
    return state.get("name") or state.get("id", "")
