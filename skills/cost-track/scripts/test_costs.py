# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of costs.py: the rates, the budget, the cost center of a domain, today's sum, the CLI.
Run: uv run --script test_costs.py   (stdlib unittest, a temp COSTS_DIR; the real journal is never touched)"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import costs  # noqa: E402

WORTH = {"value_month": 20000, "goal_month": 50000, "paid_hours_day": 5, "work_days_month": 21}


class CostsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["COSTS_DIR"] = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        costs.emit("worth.updated", dict(WORTH), actor="test")
        costs.emit("cost_center.updated", {"name": "Mukutu", "kind": "client", "pays_month": 8000}, "mukutu")
        costs.emit("cost_center.updated", {"name": "Biliboss Skills", "kind": "investment", "domains": ["tasks", "costs"]},
                   "biliboss-skills")

    def test_bind_adds_the_domain_once_and_keeps_the_center(self):
        e = costs.bind("mukutu", "sygnal")
        self.assertEqual((e["cost_center"], e["value"]["domains"], e["value"]["pays_month"]), ("mukutu", ["sygnal"], 8000))
        self.assertEqual(costs.center_of("sygnal"), "mukutu")
        self.assertIsNone(costs.bind("mukutu", "sygnal"))  # already there: no event
        costs.bind("biliboss-skills", "sygnal")  # one center per domain: it leaves mukutu
        self.assertEqual(costs.center_of("sygnal"), "biliboss-skills")
        self.assertEqual(costs.centers()["mukutu"]["domains"], [])
        with self.assertRaises(ValueError):
            costs.bind("nope", "x")

    def stop(self, center, seconds, cost, at=None):
        costs.emit("time_entry.stopped", {"domain": "x", "seconds": seconds, "rate_hour": 1, "cost": cost, "ended_by": "pause"},
                   center, at=at)

    def test_rate_of_a_client_is_the_value(self):
        self.assertAlmostEqual(costs.rate_hour("mukutu"), 20000 / 105)

    def test_rate_of_an_investment_is_the_goal(self):
        self.assertAlmostEqual(costs.rate_hour("biliboss-skills"), 50000 / 105)
        self.assertEqual(f"{costs.rate_hour('biliboss-skills'):.2f}", "476.19")

    def test_rate_of_unknown_center_is_none(self):
        self.assertIsNone(costs.rate_hour("nobody"))

    def test_budget_is_for_clients_only(self):
        self.assertAlmostEqual(costs.budget_day("mukutu"), 8000 / 21)
        self.assertIsNone(costs.budget_day("biliboss-skills"))

    def test_center_of_by_declaration(self):
        self.assertEqual(costs.center_of("anything", "mukutu"), "mukutu")

    def test_center_of_by_domains_list(self):
        self.assertEqual(costs.center_of("tasks"), "biliboss-skills")
        self.assertEqual(costs.center_of("tasks", "unknown-center"), "biliboss-skills")

    def test_center_of_none(self):
        self.assertIsNone(costs.center_of("elsewhere"))

    def test_worth_and_centers_are_the_latest(self):
        costs.emit("worth.updated", {**WORTH, "value_month": 30000})
        costs.emit("cost_center.updated", {"name": "Mukutu 2", "kind": "client", "pays_month": 9000}, "mukutu")
        self.assertEqual(costs.worth()["value_month"], 30000)
        self.assertEqual(costs.centers()["mukutu"]["name"], "Mukutu 2")

    def test_today_sums_todays_entries_only(self):
        now = datetime.now().astimezone()
        self.stop("mukutu", 3600, 190.48, at=now)
        self.stop("mukutu", 1800, 95.24, at=now)
        self.stop("mukutu", 7200, 380.96, at=now - timedelta(days=1))
        self.stop("biliboss-skills", 600, 79.37, at=now)
        self.assertEqual(costs.today("mukutu"), (5400, 285.72))
        self.assertEqual(costs.today("biliboss-skills"), (600, 79.37))
        self.assertEqual(costs.today("nobody"), (0, 0.0))

    def test_a_price_change_does_not_rewrite_the_past(self):
        self.stop("mukutu", 3600, 190.48)
        costs.emit("worth.updated", {**WORTH, "value_month": 40000})
        self.assertEqual(costs.today("mukutu"), (3600, 190.48))
        self.assertAlmostEqual(costs.rate_hour("mukutu"), 40000 / 105)

    def test_emit_writes_one_json_line_with_id_and_at(self):
        e = costs.emit("time_entry.started", {"domain": "costs"}, "mukutu", actor="me")
        last = json.loads(costs.journal_path().read_text().splitlines()[-1])
        self.assertEqual(last, e)
        self.assertTrue(e["id"] and e["at"])
        self.assertEqual((e["actor"], e["cost_center"]), ("me", "mukutu"))

    def test_emit_refuses_what_it_cannot_place(self):
        with self.assertRaises(ValueError):
            costs.emit("nope.happened", {}, "mukutu")
        with self.assertRaises(ValueError):
            costs.emit("time_entry.started", {})  # no cost center
        with self.assertRaises(ValueError):
            costs.emit("worth.updated", [1])  # not an object

    def test_cli_emit(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = costs.main(["emit", "time_entry.started", '{"domain": "costs"}', "--cost-center", "mukutu", "--actor", "cli"])
        self.assertEqual(code, 0)
        e = json.loads(out.getvalue())
        self.assertEqual((e["event"], e["actor"]), ("time_entry.started", "cli"))
        self.assertEqual(costs.events()[-1]["id"], e["id"])

    def test_running_survives_in_the_costs_folder(self):
        self.assertIsNone(costs.running())
        costs.set_running({"center": "mukutu"})
        self.assertEqual(costs.running(), {"center": "mukutu"})
        costs.set_running(None)
        self.assertIsNone(costs.running())


if __name__ == "__main__":
    unittest.main()
