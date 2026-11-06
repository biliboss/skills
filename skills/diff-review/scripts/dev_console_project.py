"""Review in the dev-console: an AI code review of a local git diff, before the delivery (design stage)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from review import TRANSITIONS, ReviewJournal  # noqa: E402,F401

NAME = "Biliboss Skills - Review"
SLUG = "review"
SOURCE = Path(__file__).parent / "review.py"  # the file with EVENTS
ENTITY = "Finding"
ENTITY_PLURAL = "achados"
ENTITIES = {"review": "Review", "finding": "Finding"}
ENTITY_KEY = "finding"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = ReviewJournal()

# A review starts on a worktree's diff.
INITIAL = ["review.started"]


def title_of(history: list[dict], state: dict) -> str:
    return state.get("text") or state.get("id", "")
