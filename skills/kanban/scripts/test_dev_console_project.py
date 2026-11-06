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

    def test_the_running_card_ticks_and_the_stage_line_is_static(self):
        html, board = self.render(rate=360.0)
        self.assertRegex(html, r'data-tick-rate="360\.000000"')  # the running cost clock, R$ per hour
        self.assertIn("data-tick-at=", html)
        self.assertIn("setInterval(tick, 1000)", html)  # the one timer (money/time only), no reload
        self.assertNotIn("data-since", html)  # the stage age is drawn by the server: static between refreshes
        self.assertIn("há 4 h no Upstream · via", html)
        self.assertIn("▶", html)

    def test_clock_states_paused_never_and_running(self):
        evs = [ev("card.created", "aaa", "2026-11-06T08:00:00-03:00", title="Via Blog", domain="via", stage="Upstream"),
               ev("card.created", "bbb", "2026-11-06T07:00:00-03:00", title="Outro", domain="kanban", stage="Todo")]
        entries = [K.TimeEntry("old", "via", "inv", NOW - timedelta(hours=3), NOW - timedelta(hours=2), False)]
        P.read_board = lambda: K.board(K.cards_from(evs), entries, {"inv": 360.0}, NOW)
        html = to_xml(P.board(None))
        self.assertIn("⏸", html)  # via cost something and the clock is elsewhere
        self.assertIn('data-clock="paused"', html)
        self.assertIn('data-clock="never"', html)
        self.assertNotRegex(html, r'data-tick-rate="[1-9]')  # nothing moves when no clock runs

    def test_agent_line_states_and_aging(self):
        evs = [ev("card.created", "aaa", "2026-11-03T08:00:00-03:00", title="Via Blog", domain="via", stage="Upstream")]
        P.read_board = lambda: K.board(K.cards_from(evs), [], {}, NOW)
        for state, mark, bold in (("trabalhando", "●", False), ("esperando você", "◆", True), ("pronto", "○", False)):
            P.agent_state = lambda card, s=state: {"session": "via-blog", "state": s, "context": "contexto 25k de 1M", "attached": True, "activity": 0}
            html = to_xml(P.board(None))
            self.assertIn(f'data-agent="{state}"', html)
            self.assertIn(mark, html)
            self.assertEqual("font-bold text-neutral-800" in html, bold)
            self.assertNotIn("você está nela", html)
        P.agent_state = lambda card: None
        self.assertNotIn("data-agent", to_xml(P.board(None)))  # no session, no line
        self.assertIn('data-aging="1"', to_xml(P.board(None)))  # 3 days in the stage

    def test_waiting_prompt_is_recognised(self):
        for text in ("↑/↓ select · Enter confirm · 1-4 quick pick · Esc/Ctrl+C deny", "1/2 answered · Tab next"):
            self.assertTrue(P.WAITING_RE.search(text), text)
        self.assertFalse(P.WAITING_RE.search("─ ready │ opus 5.5 │ 25k/1M ─"))

    def test_a_still_clock_has_rate_zero(self):
        html, _ = self.render(rate=0.0)
        self.assertNotRegex(html, r'data-tick-rate="[1-9]')

    def test_the_why_shows_under_the_title_and_the_detail_has_the_full_text(self):
        evs = [ev("card.created", "aaa", "2026-11-06T08:00:00-03:00", title="Via Blog", domain="via", stage="Upstream"),
               ev("card.described", "aaa", "2026-11-06T08:30:00-03:00", text="Por quê: ganhar corretores.\nPara quem: o corretor.")]
        board = K.board(K.cards_from(evs), [], {}, NOW)
        P.read_board = lambda: board
        html = to_xml(P.board(None))
        self.assertIn("Por quê: ganhar corretores.", html)
        self.assertNotIn(">Para quem", html)  # only in the tooltip, not as a line
        ctx = type("C", (), {"history": evs})()
        self.assertIn("Para quem: o corretor.", to_xml(P.card_history(ctx)))

    def test_the_ranked_card_is_first_and_there_are_four_columns(self):
        html, _ = self.render(rate=0.0)
        # the card titled "Outro" (not the lane "Outros"): the ranked card comes first
        self.assertLess(html.index('aria-label="abrir Via Blog"'), html.index('aria-label="abrir Outro"'))
        # one header row of stages (each lane repeats the stages as its cells)
        self.assertEqual(re.findall(r'data-stage="(\w+)"', html)[:4], ["Todo", "Upstream", "Downstream", "Feito"])

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
