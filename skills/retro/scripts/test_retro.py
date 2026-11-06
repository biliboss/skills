# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of retro.py: emit validation, projection, rejected rules, scan. Run: uv run --script test_retro.py
(stdlib unittest, a temp RETRO_DIR; the real journal is never touched)"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import retro  # noqa: E402


class RetroTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["RETRO_DIR"] = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def propose(self, lid, rule="Read before write."):
        return retro.emit("lesson.proposed", {"text": rule, "skill": "skill-smith", "rule": rule}, lid, "test")

    def test_emit_writes_a_row(self):
        row = retro.emit("retro.started", {"text": "retro"}, actor="test")
        self.assertEqual(len(row["id"]), 12)
        self.assertRegex(row["at"], r"[+-]\d\d:\d\d$")
        self.assertEqual(len(retro._all_events()), 1)

    def test_unknown_event_and_missing_text(self):
        with self.assertRaises(ValueError):
            retro.emit("retro.nope", {"text": "x"})
        with self.assertRaises(ValueError):
            retro.emit("retro.started", {})

    def test_lesson_events_need_lesson(self):
        with self.assertRaises(ValueError):
            retro.emit("lesson.proposed", {"text": "x"})

    def test_projection_status(self):
        self.propose("l1")
        retro.emit("lesson.accepted", {"text": "ok"}, "l1", "test")
        self.assertEqual(retro.lessons()[0]["status"], "accepted")
        self.assertEqual(len(retro.lessons("proposed")), 0)
        self.assertEqual(retro.lessons("accepted")[0]["skill"], "skill-smith")

    def test_rejected_rules_after_two(self):
        self.propose("l1")
        retro.emit("lesson.rejected", {"text": "no"}, "l1", "test")
        self.assertEqual(retro.rejected_rules(), [])
        self.propose("l2")
        retro.emit("lesson.rejected", {"text": "no"}, "l2", "test")
        self.assertEqual(retro.rejected_rules()[0]["rejections"], 2)

    def test_scan_marker_and_correction(self):
        f = Path(self.tmp.name) / "s.jsonl"
        rows = [
            {"type": "user", "message": {"content": "a partir de agora use uv"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "não, use o worktree"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "sempre"}]}},
            {"type": "user", "message": {"content": "sempre " + "x" * 2500}},
        ]
        f.write_text("\n".join(json.dumps(r) for r in rows))
        kinds = [(s["index"], s["kind"]) for s in retro.scan(str(f))]
        self.assertEqual(kinds, [(0, "marker"), (2, "correction")])


if __name__ == "__main__":
    unittest.main()
