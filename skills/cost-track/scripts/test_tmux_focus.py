# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of tmux_focus.py: the clock follows the attached tmux session.
Run: uv run --script test_tmux_focus.py   (temp COSTS_DIR, KANBAN_DIR, DEVC_DOMAINS, TMUX_CONF; the real ones are never touched)"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import costs  # noqa: E402
import tmux_focus as tf  # noqa: E402

spec = importlib.util.spec_from_file_location("kanban_t", HERE.parent.parent / "kanban" / "scripts" / "kanban.py")
kanban = importlib.util.module_from_spec(spec)
sys.modules["kanban_t"] = kanban
spec.loader.exec_module(kanban)

PROJECT = 'SLUG = "via-blog"\nCOST_CENTER = "viacorretor"\n'


class TmuxFocusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        for k, v in {"COSTS_DIR": t / "costs", "KANBAN_DIR": t / "kanban", "DEVC_DOMAINS": t / "domains.txt",
                     "TMUX_CONF": t / "tmux.conf", "TMUX_BIN": "/usr/bin/true"}.items():
            os.environ[k] = str(v)
            self.addCleanup(os.environ.pop, k, None)
        (t / "via_project.py").write_text(PROJECT)
        (t / "domains.txt").write_text(str(t / "via_project.py") + "\n")
        costs.emit("worth.updated", {"value_month": 20000, "goal_month": 50000, "paid_hours_day": 5, "work_days_month": 21})
        costs.emit("cost_center.updated", {"name": "Via Corretor", "kind": "investment"}, "viacorretor")
        self.card = kanban.create("Via Blog", "via-blog", "Downstream")["card_id"]
        kanban.create("Todo thing", "kanban", "Todo")

    def entries(self, kind):
        return [e for e in costs.events() if e["event"] == f"time_entry.{kind}"]

    def test_attach_starts_in_the_cards_domain(self):
        tf.focus("via-blog")
        run = costs.running()
        self.assertEqual((run["domain"], run["center"], run["card"]), ("via-blog", "viacorretor", self.card))
        self.assertEqual(self.entries("started")[-1]["value"]["card"], self.card)

    def test_switch_away_stops_and_back_starts_a_new_entry(self):
        tf.focus("via-blog")
        tf.focus("bili")
        self.assertIsNone(costs.running())
        self.assertEqual(len(self.entries("stopped")), 1)
        self.assertEqual(self.entries("stopped")[0]["value"]["ended_by"], "tmux")
        tf.focus("via-blog")
        self.assertEqual(len(self.entries("started")), 2)
        self.assertIsNotNone(costs.running())

    def test_detach_stops(self):
        tf.focus("via-blog")
        tf.focus("-")
        self.assertIsNone(costs.running())
        self.assertEqual(len(self.entries("stopped")), 1)

    def test_unknown_and_todo_sessions_stop(self):
        tf.focus("via-blog")
        tf.focus("nothing-like-a-card")
        self.assertIsNone(costs.running())
        tf.focus("via-blog")
        tf.focus("todo-thing")  # a Todo card is not worked now
        self.assertIsNone(costs.running())

    def test_repeat_attach_does_not_duplicate(self):
        for _ in range(3):
            tf.focus("via-blog")
        self.assertEqual(len(self.entries("started")), 1)
        self.assertEqual(len(self.entries("stopped")), 0)

    def test_stop_when_nothing_runs_writes_nothing(self):
        tf.focus("bili")
        tf.focus("-")
        self.assertEqual(costs.events()[-1]["event"], "cost_center.updated")

    def test_main_never_fails(self):
        self.assertEqual(tf.main(["tmux-focus", "via-blog"]), 0)
        self.assertEqual(tf.main(["tmux-focus"]), 0)
        self.assertIsNone(costs.running())

    def test_install_is_idempotent_and_uninstall_removes(self):
        conf = Path(os.environ["TMUX_CONF"])
        conf.write_text("set -g mouse on\n")
        for _ in range(2):
            tf.main(["tmux-install"])
        text = conf.read_text()
        self.assertEqual(text.count(tf.BEGIN), 1)
        for h in tf.HOOKS:
            self.assertIn(f"set-hook -g {h}[{tf.HOOK_INDEX}]", text)
        self.assertIn("tmux-focus -", text)
        tf.main(["tmux-uninstall"])
        self.assertEqual(conf.read_text().strip(), "set -g mouse on")


if __name__ == "__main__":
    unittest.main()
