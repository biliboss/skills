# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("self_learning", Path(__file__).with_name("self_learning.py"))
learning = importlib.util.module_from_spec(spec)
spec.loader.exec_module(learning)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skill = self.root / "example" / "SKILL.md"
        self.skill.parent.mkdir()
        self.skill.write_text("Read state before sending work.\n")
        self.session = self.root / "session.jsonl"
        self.rows = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "load", "name": "Read", "input": {"file_path": str(self.skill)}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "load", "content": self.skill.read_text()}]}},
            {"type": "user", "message": {"content": "Always inspect state before each send, including retries."}},
        ]
        self.write_session()

    def tearDown(self):
        self.temp.cleanup()

    def write_session(self):
        self.session.write_text("\n".join(json.dumps(row) for row in self.rows))

    def test_completed_load_and_retro_signal(self):
        found = learning.scan(self.session, "example")
        self.assertEqual(len(found["loads"]), 1)
        self.assertEqual(found["signals"][0]["line"], 3)

    def test_failed_load_and_mentions_are_not_loads(self):
        self.rows[1]["message"]["content"][0]["is_error"] = True
        self.write_session()
        self.assertEqual(learning.scan(self.session, "example")["loads"], [])
        self.rows = [{"type": "user", "message": {"content": "Always load example/SKILL.md"}}]
        self.write_session()
        self.assertEqual(learning.scan(self.session, "example")["loads"], [])

    def test_explicit_apply_rolls_back_failed_doctor(self):
        old = self.skill.read_text()
        proposal = learning.propose(self.skill, self.session, 3, old.strip(), "Inspect state before every send, including retries.")
        path = self.root / "proposal.json"
        path.write_text(json.dumps(proposal))
        result = learning.apply(path, [sys.executable, "-c", "raise SystemExit(1)"])
        self.assertFalse(result["applied"])
        self.assertEqual(self.skill.read_text(), old)
        result = learning.apply(path, [sys.executable, "-c", "pass"])
        self.assertTrue(result["applied"])
        self.assertIn("every send", self.skill.read_text())
        with self.assertRaisesRegex(ValueError, "changed since"):
            learning.apply(path, [sys.executable, "-c", "pass"])

    def test_skill_tool_success_and_unpaired_calls(self):
        self.rows[0]["message"]["content"][0].update(name="Skill", input={"skill": "plugin:example"})
        self.write_session()
        self.assertEqual(len(learning.scan(self.session, "example")["loads"]), 1)
        self.rows.pop(1)
        self.write_session()
        self.assertEqual(learning.scan(self.session, "example")["loads"], [])

    def test_timeout_and_missing_command_restore_original(self):
        old = self.skill.read_text()
        proposal = learning.propose(self.skill, self.session, 3, old.strip(), "Inspect every send.")
        path = self.root / "proposal.json"
        path.write_text(json.dumps(proposal))
        for command in ([str(self.root / "missing-command")], [sys.executable, "-c", "import time; time.sleep(1)"]):
            result = learning.apply(path, command, timeout=0.01)
            self.assertFalse(result["applied"])
            self.assertEqual(self.skill.read_text(), old)
        with self.assertRaisesRegex(ValueError, "explicit doctor"):
            learning.apply(path, [])

    def test_stale_or_forged_evidence_rejected(self):
        proposal = learning.propose(self.skill, self.session, 3, self.skill.read_text().strip(), "Inspect every send.")
        proposal["evidence"]["signal"]["quote"] = "invented"
        path = self.root / "proposal.json"
        path.write_text(json.dumps(proposal))
        with self.assertRaisesRegex(ValueError, "does not match"):
            learning.apply(path, [sys.executable, "-c", "pass"])


if __name__ == "__main__":
    unittest.main()
