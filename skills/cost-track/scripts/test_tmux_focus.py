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

    def test_window_card_wins_over_the_session_name(self):
        tf.focus("bili", self.card[:8])  # the session is not a card; the active window's @card is
        run = costs.running()
        self.assertEqual((run["domain"], run["card"]), ("via-blog", self.card))
        tf.focus("bili", "")  # window without @card, session not a card: stops
        self.assertIsNone(costs.running())

    def test_window_change_inside_one_session_switches_the_clock(self):
        tf.focus("work", self.card[:8])
        self.assertIsNotNone(costs.running())
        tf.focus("work", "")
        self.assertIsNone(costs.running())
        self.assertEqual(len(self.entries("started")), 1)

    def test_unknown_window_card_falls_back_to_the_session_name(self):
        tf.focus("via-blog", "deadbeef")
        self.assertEqual(costs.running()["card"], self.card)

    def test_main_parses_card_flag_and_hooks_include_window_change(self):
        tf.main(["tmux-focus", "bili", f"--card={self.card[:8]}"])
        self.assertEqual(costs.running()["card"], self.card)
        self.assertIn("session-window-changed", tf.HOOKS)
        self.assertIn("--card=#{@card}", tf._cmd("costs.sh", tf.WIN))

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
        self.assertIn("session-window-changed[", text)
        tf.main(["tmux-uninstall"])
        self.assertEqual(conf.read_text().strip(), "set -g mouse on")


class ClockLogTest(TmuxFocusTest):
    """The log chain: hook -> decision -> running written/removed, and the bash trace/check/simulate."""

    def setUp(self):
        super().setUp()
        self.log = Path(self.tmp.name) / "clock.log"
        os.environ["CLOCK_LOG"] = str(self.log)
        self.addCleanup(os.environ.pop, "CLOCK_LOG", None)
        self.sh = str(HERE / "costs.sh")

    def lines(self):
        import json
        return [json.loads(l) for l in self.log.read_text().splitlines()]

    def bash(self, *args):
        import subprocess
        return subprocess.run([self.sh, *args], capture_output=True, text=True, env=dict(os.environ, TMUX_BIN="/usr/bin/false"))

    def test_start_then_stop_log_every_hop(self):
        tf.main(["tmux-focus", "via-blog"])
        tf.main(["tmux-focus", "bili"])
        hops = [(l["hop"], l.get("action")) for l in self.lines()]
        self.assertEqual(hops, [("hook", None), ("running_written", None), ("decision", "start"),
                                ("hook", None), ("running_removed", None), ("decision", "stop")])
        dec = [l for l in self.lines() if l["hop"] == "decision"][0]
        self.assertEqual((dec["session"], dec["domain"], dec["card"]), ("via-blog", "via-blog", self.card))

    def test_noop_when_already_running(self):
        tf.focus("via-blog")
        tf.focus("via-blog")
        self.assertEqual([l["action"] for l in self.lines() if l["hop"] == "decision"], ["start", "noop"])

    def test_trace_prints_last_lines_and_check_compares(self):
        tf.main(["tmux-focus", "via-blog"])
        self.assertEqual(len(self.bash("trace", "2").stdout.splitlines()), 2)
        self.assertEqual(self.bash("check", "via-blog").returncode, 0)
        self.assertEqual(self.bash("check", "bili").returncode, 1)  # running for another session
        tf.main(["tmux-focus", "bili"])
        self.assertEqual(self.bash("check", "bili").returncode, 0)  # stopped is right for a non-card session
        tf.focus("via-blog")
        (costs.costs_dir() / "running.json").unlink()  # the log says it started, the file is gone
        self.assertEqual(self.bash("check", "via-blog").returncode, 1)

    def test_simulate_runs_the_hook_path(self):
        r = self.bash("simulate", "via-blog")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines()[0]["source"], "simulate")
        self.assertIsNotNone(costs.running())


if __name__ == "__main__":
    unittest.main()
