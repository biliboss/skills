# /// script
# requires-python = ">=3.10"
# dependencies = ["python-fasthtml>=0.14", "monsterui>=1.0.48"]
# ///
"""Tests of the Quadro's rendered HTML: the data attributes the browser ticks from (since, rate), the journal stamp
the board watches, and the order of the cards. Run: uv run --script test_dev_console_project.py (invented data)."""
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["KANBAN_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).parent))
import dev_console_project as P  # noqa: E402
import kanban as K  # noqa: E402
from fasthtml.common import to_xml  # noqa: E402

BRT = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=BRT)


def ev(kind, card, at, **value):
    return {"id": f"{card}{at}", "event": kind, "at": at, "actor": "t", "card_id": card, "value": value}


class BoardHtmlTest(unittest.TestCase):
    def render(self, rate):
        evs = [ev("card.created", "aaa", "2026-11-06T08:00:00-03:00", title="Via Blog", domain="via", stage="Upstream"),
               ev("card.created", "bbb", "2026-11-06T07:00:00-03:00", title="Outro", domain="kanban", stage="Upstream"),
               ev("card.prioritized", "aaa", "2026-11-06T09:00:00-03:00", position=0, stage="Upstream")]
        entries = [K.TimeEntry("running", "via", "inv", NOW - timedelta(hours=1), NOW, True)] if rate else []
        board = K.board(K.cards_from(evs), entries, {"inv": rate or 0.0}, NOW)
        P.read_board = lambda: board
        return to_xml(P.board(None)), board

    def test_the_card_carries_its_since_and_the_clock_rate(self):
        html, board = self.render(rate=360.0)
        since_ms = str(int(datetime(2026, 11, 6, 8, 0, tzinfo=BRT).timestamp() * 1000))
        self.assertIn(f'data-since="{since_ms}"', html)
        self.assertIn('data-domain="via"', html)
        self.assertRegex(html, r'data-tick-rate="360\.000000"')  # the running cost clock, R$ per hour
        self.assertIn("data-tick-at=", html)
        self.assertIn("setInterval(both, 1000)", html)  # the one timer, no reload

    def test_a_still_clock_has_rate_zero(self):
        html, _ = self.render(rate=0.0)
        self.assertNotRegex(html, r'data-tick-rate="[1-9]')

    def test_the_ranked_card_is_first_and_there_are_four_columns(self):
        html, _ = self.render(rate=0.0)
        self.assertLess(html.index("Via Blog"), html.index("Outro"))
        self.assertEqual([m for m in re.findall(r'data-stage="(\w+)"', html)], ["Todo", "Upstream", "Downstream", "Feito"])

    def test_the_header_shows_count_over_limit_and_marks_what_is_over(self):
        os.environ["KANBAN_CONFIG"] = str(Path(tempfile.gettempdir()) / "no-such-kanban-config.json")  # the default limits
        html, _ = self.render(rate=0.0)  # two cards in Upstream, limit 1: over
        self.assertIn("2/1", html)
        self.assertEqual(html.count('data-over="1"'), 1)
        self.assertIn("font-bold", html)
        evs = [ev("card.created", "aaa", "2026-11-06T08:00:00-03:00", title="Via Blog", domain="via", stage="Upstream")]
        P.read_board = lambda: K.board(K.cards_from(evs), [], {}, NOW)
        html = to_xml(P.board(None))
        self.assertIn("1/1", html)  # full, not over: no mark
        self.assertNotIn('data-over="1"', html)
        self.assertNotIn("0/", html)  # the stages with no limit show only the count

    def test_the_board_watches_the_journal(self):
        html, _ = self.render(rate=0.0)
        self.assertIn("kanban-journal", html)  # the event that redraws the board
        self.assertIn("JournalStamp", html)  # the 2 s poll's target
        self.assertRegex(html, r'data-stamp="\d+"')
        before = P._stamp()
        K.create("x", "kanban")
        self.assertNotEqual(P._stamp(), before)  # an event appended changes the stamp
        self.assertIn(f'data-stamp="{P._stamp()}"', to_xml(P.journal_stamp(None)))


if __name__ == "__main__":
    unittest.main()
