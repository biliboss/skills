# /// script
# requires-python = ">=3.10"
# dependencies = ["starlette", "httpx", "python-fasthtml>=0.14"]
# ///
"""Tests of console_focus.py: the journal, the by-guard, the stack (set / back), the card in Doing, and the routes, on
temp DEV_CONSOLE_FOCUS_DIR, KANBAN_DIR and COSTS_DIR with invented cards.
Run: uv run --script test_console_focus.py"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
import console_focus as F  # noqa: E402

BOARD = "/domain/kanban?tab=Quadro"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.env = {k: os.environ.get(k) for k in ("DEV_CONSOLE_FOCUS_DIR", "KANBAN_DIR", "COSTS_DIR")}
        os.environ.update(DEV_CONSOLE_FOCUS_DIR=str(root / "focus"), KANBAN_DIR=str(root / "kanban"), COSTS_DIR=str(root / "costs"))
        self.K = F.kanban()
        self.assertIsNotNone(self.K, "kanban.py beside this skill")

    def tearDown(self):
        for k, v in self.env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.tmp.cleanup()

    def card(self, title, domain="via", stage="Downstream"):
        return self.K.create(title, domain, stage, actor="gabriel")["card_id"]


class Journal(Base):
    def test_set_appends_one_line_and_show_reads_it(self):
        F.set_focus("Revisar o grafo do Via", "via", None, "bili")
        lines = F.journal_path().read_text().splitlines()
        self.assertEqual(len(lines), 1)
        e = json.loads(lines[0])
        self.assertEqual((e["event"], e["actor"]), ("focus.set", "bili"))
        self.assertEqual(e["value"], {"text": "Revisar o grafo do Via", "target": "via", "card": None, "by": "bili"})
        self.assertEqual(F.snapshot(BOARD)["focus"]["text"], "Revisar o grafo do Via")

    def test_a_broken_line_is_skipped(self):
        F.set_focus("um", "via", None, "gabriel")
        with open(F.journal_path(), "a") as f:
            f.write("not json\n")
        self.assertEqual(F.current(F.events()).text, "um")

    def test_targets(self):
        self.assertEqual([F.kind(t) for t in ("kanban", "via", "via/listing.shared/Funnel", "/agents", "https://x.dev/a")],
                         ["kanban", "slug", "widget", "url", "url"])
        for bad in ("", "Via Corretor", "a/b", "//evil.example/x", "javascript:alert(1)"):
            with self.assertRaises(ValueError):
                F.kind(bad)
        with self.assertRaises(ValueError):
            F.set_focus("x", "Via Corretor", None, "bili")
        with self.assertRaises(ValueError):
            F.set_focus("  ", "via", None, "bili")
        self.assertFalse(F.journal_path().exists())

    def test_where_a_focus_goes_and_what_the_home_embeds(self):
        w = F.Focus("f", "via/listing.shared/Funnel")
        self.assertEqual(F.go_url(w, BOARD), "/domain/via?ev=listing.shared&w=Funnel")
        self.assertEqual(F.embed_url(w, BOARD), "/domain/via/w/_/listing.shared/Funnel")
        self.assertEqual(F.embed_url(F.Focus("f", "via"), BOARD), "/domain/via?embed=graph")
        self.assertEqual(F.embed_url(F.Focus("f", "/domain/via?ev=a"), BOARD), "/domain/via?ev=a&embed=1")
        self.assertEqual(F.go_url(F.DEFAULT, BOARD), BOARD)


class Guard(Base):
    def test_only_gabriel_or_bili_move_the_focus(self):
        for by in ("hacker", "agent", "Bili", "", "subagent"):
            with self.assertRaises(PermissionError):
                F.set_focus("x", "via", None, by)
        F.set_focus("x", "via", None, "gabriel")
        with self.assertRaises(PermissionError):
            F.back("hipster")
        self.assertEqual(len(F.events()), 1)

    def test_the_cli_refuses_with_exit_3(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = F.main(["set", "x", "--target", "via", "--by", "hacker"])
        self.assertEqual(code, 3)
        self.assertIn("only the owner's conversation", err.getvalue())
        self.assertEqual(F.events(), [])


class Stack(Base):
    def test_the_default_is_the_kanban_board(self):
        self.assertEqual(F.current([]), F.DEFAULT)
        self.assertEqual(F.DEFAULT.target, "kanban")
        s = F.snapshot(BOARD)
        self.assertEqual((s["focus"]["target"], s["focus"]["default"], s["home"], s["depth"]), ("kanban", True, BOARD, 0))

    def test_back_pops_down_to_the_kanban_and_then_refuses(self):
        F.set_focus("a", "via", None, "bili")
        F.set_focus("b", "tasks", None, "gabriel")
        self.assertEqual(F.current(F.events()).text, "b")
        F.back("bili")
        self.assertEqual(F.current(F.events()).text, "a")
        F.back("gabriel")
        self.assertEqual(F.current(F.events()), F.DEFAULT)
        with self.assertRaises(ValueError):
            F.back("bili")

    def test_a_back_on_an_empty_stack_in_the_journal_changes_nothing(self):
        evs = [{"event": "focus.back"}, {"event": "focus.set", "value": {"text": "a", "target": "via"}}]
        self.assertEqual(F.current(evs).text, "a")

    def test_history_is_newest_first_without_the_current_and_repeats(self):
        for i, t in enumerate(["via", "tasks", "via", "costs", "kanban", "a", "b", "c"]):
            F.set_focus(f"f{i}", t, None, "bili")
        h = F.history(F.events())
        self.assertEqual([x.target for x in h], ["b", "a", "kanban", "costs", "via"])
        self.assertNotIn("c", [x.target for x in h])
        self.assertEqual(len(F.snapshot(BOARD)["history"]), 5)


class Home(Base):
    def test_without_a_card_in_doing_the_home_is_the_board(self):
        self.card("Ainda descobrindo", stage="Upstream")
        F.set_focus("o grafo do Via", "via", None, "bili")
        s = F.snapshot(BOARD)
        self.assertIsNone(s["card"])
        self.assertEqual(s["home"], BOARD)

    def test_with_a_card_in_doing_the_home_holds_the_focus(self):
        cid = self.card("Focus home")
        F.set_focus("o grafo do Via", "via", "Focus home", "bili")  # a title is resolved to the card's id
        self.assertEqual(F.current(F.events()).card, cid)
        s = F.snapshot(BOARD)
        self.assertEqual(s["home"], "/home")
        self.assertEqual((s["card"]["title"], s["card"]["stage"], s["card"]["domain"]), ("Focus home", "Downstream", "via"))
        self.assertEqual(s["focus"]["embed"], "/domain/via?embed=graph")

    def test_the_kanban_as_focus_is_the_board_even_with_a_card_in_doing(self):
        self.card("Focus home")
        F.set_focus("o quadro", "kanban", None, "gabriel")
        self.assertEqual(F.snapshot(BOARD)["home"], BOARD)

    def test_the_focus_card_wins_among_cards_in_doing_else_the_last_in(self):
        a = self.card("A")
        self.card("B")
        F.set_focus("x", "via", None, "bili")
        self.assertEqual(F.snapshot(BOARD)["card"]["title"], "B")
        F.set_focus("y", "via", a, "bili")
        self.assertEqual(F.snapshot(BOARD)["card"]["title"], "A")

    def test_an_unknown_card_is_refused(self):
        with self.assertRaises(ValueError):
            F.set_focus("x", "via", "no such card", "bili")
        self.assertEqual(F.events(), [])

    def test_the_cost_clock_counts_only_the_doing_stays(self):
        K, t0 = self.K, datetime(2026, 11, 6, 9, 0).astimezone()
        evs = [{"id": "1", "event": "card.created", "at": t0.isoformat(), "actor": "g", "card_id": "c1",
                "value": {"title": "C", "domain": "via", "stage": "Upstream"}},
               {"id": "2", "event": "card.moved", "at": (t0 + timedelta(hours=1)).isoformat(), "actor": "g", "card_id": "c1",
                "value": {"stage": "Downstream", "previous": "Upstream"}}]
        card = K.card_from(evs)
        now = t0 + timedelta(hours=3)
        entries = [K.TimeEntry("e1", "via", "house", t0, t0 + timedelta(hours=2)),  # half of it in Doing
                   K.TimeEntry("e2", "tasks", "house", t0, now),  # another domain
                   K.TimeEntry("running", "via", "house", now - timedelta(minutes=30), now, True)]
        m = F.doing_money(card, "Downstream", entries, {"house": 120.0}, now)
        self.assertEqual(m, {"seconds": 5400.0, "brl": 180.0, "live_rate_hour": 120.0})
        today = F.doing_money(card, "Downstream", entries, {"house": 120.0}, now, since=now - timedelta(minutes=10))
        self.assertEqual(today["seconds"], 600.0)

    def test_the_doing_stage_is_doing_when_the_board_has_it(self):
        self.assertEqual(F.doing_stage(["Upstream", "Downstream", "Feito"]), "Downstream")
        self.assertEqual(F.doing_stage(["To Do", "Doing", "Downstream"]), "Doing")


def client():
    """The routes on a bare Starlette app, with a shim for the console's `rt` (query params become arguments)."""
    routes = []

    def rt(path):
        def deco(fn):
            async def endpoint(request):
                out = fn(**dict(request.query_params))
                if isinstance(out, Response):
                    return out
                from fasthtml.common import to_xml
                return Response("".join(to_xml(x) for x in out), media_type="text/html")
            routes.append(Route(path, endpoint))
            return fn
        return deco

    app = SimpleNamespace(hdrs=[])
    rec = SimpleNamespace(recorder_dir=lambda: Path(os.environ["DEV_CONSOLE_FOCUS_DIR"]) / "rec", read_lines=lambda: [])
    ui = SimpleNamespace(css="", status_bar=lambda name: "", switcher=lambda: "", switcher_js=lambda href: "", board=lambda: BOARD,
                         recorder=rec, data=lambda href: {})
    F.register(app, rt, lambda data, status=200: JSONResponse(data, status_code=status), ui)
    return app, TestClient(Starlette(routes=routes))


class Routes(Base):
    def test_agent_focus_and_the_g_h_key(self):
        app, c = client()
        self.assertTrue(any("__devconsoleGH" in str(h) for h in app.hdrs))
        r = c.get("/agent/focus")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()) >= {"focus", "card", "history", "cost_today", "home"}, True)
        self.assertEqual(r.json()["focus"]["target"], "kanban")

    def test_home_redirects_to_the_board_then_shows_the_card_and_the_focus(self):
        _, c = client()
        r = c.get("/home", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, BOARD))
        self.card("Focus home")
        F.set_focus("o grafo do Via", "via", "Focus home", "bili")
        F.set_focus("um widget", "via/listing.shared/Funnel", "Focus home", "bili")
        F.back("bili")
        r = c.get("/home")
        self.assertEqual(r.status_code, 200)
        for text in ("Focus home", "o grafo do Via", 'src="/domain/via?embed=graph"', 'data-go="/domain/via?ev=listing.shared&amp;w=Funnel"'):
            self.assertIn(text, r.text)
        self.assertEqual(c.get("/agent/focus").json()["cost_today"], {"seconds": 0.0, "brl": 0.0})

    def test_another_site_is_framed_in_a_sandbox(self):
        _, c = client()
        self.card("Focus home")
        F.set_focus("a página do produto", "https://example.com/p", "Focus home", "bili")
        html = c.get("/home").text
        self.assertIn('sandbox="allow-scripts allow-forms"', html)
        self.assertIn('src="https://example.com/p"', html)

    def test_a_shot_is_served_only_by_a_recorder_name(self):
        _, c = client()
        self.assertEqual(c.get("/home/shot", params={"at": "../../etc/passwd"}).status_code, 404)
        shots = Path(os.environ["DEV_CONSOLE_FOCUS_DIR"]) / "rec" / "shots"
        shots.mkdir(parents=True)
        (shots / "20261106T120000.000Z.png").write_bytes(b"\x89PNG")
        self.assertEqual(c.get("/home/shot", params={"at": "20261106T120000.000Z"}).status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=1)
