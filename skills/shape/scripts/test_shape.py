# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of shape.py: emit validation, projection, listing. Run: uv run --script test_shape.py
(stdlib unittest, a temp SHAPE_DIR; the real journal is never touched)"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import shape  # noqa: E402


class ShapeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SHAPE_DIR"] = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def emit(self, event, value, sid="s1"):
        return shape.emit(event, value, sid, "test")

    def test_emit_writes_a_row(self):
        row = self.emit("request.received", {"text": "faz um site"})
        self.assertEqual(len(row["id"]), 12)
        self.assertRegex(row["at"], r"[+-]\d\d:\d\d$")
        self.assertEqual(len(shape._all_events()), 1)

    def test_unknown_event_and_bad_values_are_refused(self):
        with self.assertRaises(ValueError):
            self.emit("request.nope", {"text": "x"})
        with self.assertRaises(ValueError):
            self.emit("piece.routed", {"piece": "magic"})
        with self.assertRaises(ValueError):
            self.emit("work.delegated", {"to": "nobody"})
        with self.assertRaises(ValueError):
            self.emit("request.received", {})
        with self.assertRaises(ValueError):
            shape.emit("request.received", {"text": "x"}, "")

    def test_projection_follows_the_story(self):
        self.emit("request.received", {"text": "faz um site"})
        self.emit("piece.routed", {"piece": "pelo-resultado"})
        self.emit("understanding.taught_back", {"text": "um site para X"})
        s = shape.shapings()[0]
        self.assertEqual((s["request"], s["piece"], s["status"]), ("faz um site", "pelo-resultado", "taught_back"))
        self.emit("understanding.confirmed", {"text": "ok"})
        self.emit("work.delegated", {"to": "subagent"})
        s = shape.ShapeJournal().read({"id": "s1"})
        self.assertEqual((s["status"], s["delegated_to"]), ("delegated", "subagent"))

    def test_list_filters_by_status_and_keeps_shapings_apart(self):
        self.emit("request.received", {"text": "a"}, "a")
        self.emit("request.received", {"text": "b"}, "b")
        self.emit("piece.routed", {"piece": "direct"}, "b")
        self.assertEqual(len(shape.shapings()), 2)
        self.assertEqual([s["id"] for s in shape.shapings("routed")], ["b"])

    def test_transitions_only_name_real_events(self):
        valid = {f"{d}.{k}" for d, kinds in shape.EVENTS.items() for k in kinds.values()}
        for src, dsts in shape.TRANSITIONS.items():
            self.assertIn(src, valid)
            self.assertTrue(set(dsts) <= valid)

    def test_cli_main(self):
        self.assertEqual(shape.main(["emit", "request.received", '{"text":"x"}', "--shaping", "z", "--actor", "t"]), 0)
        self.assertEqual(shape.main(["emit", "piece.routed", '{"piece":"x"}', "--shaping", "z", "--actor", "t"]), 2)
        self.assertEqual(shape.main(["list"]), 0)


if __name__ == "__main__":
    unittest.main()
