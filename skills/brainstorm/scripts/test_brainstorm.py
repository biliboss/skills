# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of brainstorm.py: emit validation, projection, causal graph. Run: uv run --script test_brainstorm.py
(stdlib unittest, a temp BRAINSTORM_DIR; the real journal is never touched)"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brainstorm  # noqa: E402


class BrainstormTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BRAINSTORM_DIR"] = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def emit(self, event, value, session="s1"):
        return brainstorm.emit(event, value, session, "test")

    def test_emit_writes_a_row(self):
        row = self.emit("session.started", {"text": "uma ideia"})
        self.assertEqual(len(row["id"]), 12)
        self.assertRegex(row["at"], r"[+-]\d\d:\d\d$")
        self.assertEqual(len(brainstorm._all_events()), 1)

    def test_unknown_event_missing_session_and_text(self):
        with self.assertRaises(ValueError):
            self.emit("session.nope", {"text": "x"})
        with self.assertRaises(ValueError):
            brainstorm.emit("session.started", {"text": "x"}, "")
        with self.assertRaises(ValueError):
            self.emit("session.started", {})

    def test_cynefin_domain_is_checked(self):
        self.emit("problem.classified", {"domain": "complex"})
        with self.assertRaises(ValueError):
            self.emit("problem.classified", {"domain": "hard"})

    def test_link_polarity_and_loop_kind_are_checked(self):
        self.emit("link.added", {"from": "a", "to": "b", "polarity": "-"})
        with self.assertRaises(ValueError):
            self.emit("link.added", {"from": "a", "to": "b", "polarity": "*"})
        with self.assertRaises(ValueError):
            self.emit("loop.identified", {"kind": "X"})
        self.emit("loop.identified", {"kind": "R", "variables": ["a", "b"]})

    def test_leverage_level_range(self):
        self.emit("leverage.ranked", {"level": 12, "text": "paradigms"})
        for bad in (0, 13, "3"):
            with self.assertRaises(ValueError):
                self.emit("leverage.ranked", {"level": bad})

    def test_projection(self):
        self.emit("session.started", {"text": "app de tarefas"})
        self.emit("problem.classified", {"domain": "complex"})
        self.emit("variable.added", {"name": "a"})
        self.emit("link.added", {"from": "a", "to": "b", "polarity": "+"})
        self.emit("approach.chosen", {"text": "Decidi X porque Y"})
        self.emit("session.started", {"text": "outra"}, "s2")
        s1 = [s for s in brainstorm.sessions() if s["id"] == "s1"][0]
        self.assertEqual((s1["idea"], s1["cynefin"], s1["variables"], s1["links"], s1["status"]),
                         ("app de tarefas", "complex", 1, 1, "chosen"))
        self.assertEqual(len(brainstorm.sessions()), 2)
        self.assertEqual(len(brainstorm.sessions("started")), 1)

    def test_causal_graph(self):
        self.emit("variable.added", {"name": "pressa"})
        self.emit("link.added", {"from": "pressa", "to": "bugs", "polarity": "+"})
        self.emit("link.added", {"from": "bugs", "to": "pressa", "polarity": "-"})
        self.emit("loop.identified", {"kind": "B", "variables": ["pressa", "bugs"]})
        self.emit("variable.added", {"name": "outra"}, "s2")
        g = brainstorm.graph("s1")
        self.assertEqual(g["nodes"], ["pressa", "bugs"])
        self.assertEqual([x["polarity"] for x in g["edges"]], ["+", "-"])
        self.assertEqual(g["loops"], [{"kind": "B", "variables": ["pressa", "bugs"]}])

    def test_transitions_name_real_events(self):
        valid = {f"{d}.{k}" for d, kinds in brainstorm.EVENTS.items() for k in kinds.values()}
        for src, targets in brainstorm.TRANSITIONS.items():
            self.assertIn(src, valid)
            for t in targets:
                self.assertIn(t, valid)

    def test_empty_journal(self):
        self.assertEqual(brainstorm.sessions(), [])
        self.assertEqual(brainstorm.graph("x"), {"nodes": [], "edges": [], "loops": []})

    def test_cli_main(self):
        self.assertEqual(brainstorm.main(["emit", "session.started", '{"text":"x"}', "--session", "s", "--actor", "t"]), 0)
        self.assertEqual(brainstorm.main(["emit", "session.started", "{}", "--session", "s", "--actor", "t"]), 2)
        self.assertEqual(brainstorm.main(["sessions"]), 0)
        self.assertEqual(brainstorm.main(["graph", "s"]), 0)


if __name__ == "__main__":
    unittest.main()
