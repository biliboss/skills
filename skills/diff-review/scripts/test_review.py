# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of review.py: emit validation, projection, dedupe, fail-closed parsing, exit codes and `run` with a fake
engine (DIFF_REVIEW_FAKE_OUTPUT). Run: uv run --script test_review.py (stdlib unittest, temp REVIEW_DIR and temp git
repo; no model is ever called)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import review  # noqa: E402

GOOD = {"findings": [
    {"file": "app.py", "line": 2, "severity": "blocker", "confidence": 90, "text": "URL without scheme check",
     "scenario": "javascript: URL", "rule": ""},
    {"file": "app.py", "line": 3, "severity": "minor", "confidence": 50, "text": "low confidence", "scenario": "x"},
], "declined": ["generated code"]}


def fenced(data) -> str:
    return "Thinking...\n```json\n" + json.dumps(data) + "\n```\n"


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                            GIT_COMMITTER_EMAIL="t@t"))


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        os.environ["REVIEW_DIR"] = str(root / "journal")
        self.repo = root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "app.py").write_text("a = 1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "checkout", "-q", "-b", "feat")
        (self.repo / "app.py").write_text("a = 1\nurl = input()\nprint(url)\n")
        git(self.repo, "commit", "-qam", "change")
        self.fake = root / "fake.txt"
        os.environ["DIFF_REVIEW_FAKE_OUTPUT"] = str(self.fake)
        self.addCleanup(os.environ.pop, "DIFF_REVIEW_FAKE_OUTPUT", None)

    def run_review(self, data=None, text=None):
        self.fake.write_text(text if text is not None else fenced(data))
        return review.run(str(self.repo), "main", "t1")

    # emit and projection
    def test_emit_validation(self):
        with self.assertRaises(ValueError):
            review.emit("review.nope", {"text": "x"})
        with self.assertRaises(ValueError):
            review.emit("review.started", {})
        with self.assertRaises(ValueError):
            review.emit("finding.reported", {"text": "x"})
        row = review.emit("review.started", {"text": "x"}, review="r1")
        self.assertEqual(len(row["id"]), 12)
        self.assertRegex(row["at"], r"[+-]\d\d:\d\d$")

    def test_projection_and_close(self):
        review.emit("finding.reported", {"text": "t", "file": "a.py", "line": 1, "severity": "minor"}, finding="f1")
        self.assertEqual(review.findings(open_only=True)[0]["status"], "reported")
        review.close("f1", "dismiss", "meh", {"reason": "intended"})
        self.assertEqual(review.findings()[0]["status"], "dismissed")
        self.assertEqual(review.findings()[0]["reason"], "intended")
        self.assertEqual(review.findings(open_only=True), [])
        with self.assertRaises(ValueError):
            review.close("f1", "fix", "again")
        with self.assertRaises(ValueError):
            review.close("nope", "fix", "x")

    def test_dismissals_count(self):
        for i in range(3):
            review.emit("finding.reported", {"text": f"t{i}", "file": "a", "severity": "minor"}, finding=f"f{i}")
            review.close(f"f{i}", "dismiss", "x", {"reason": "false_positive"})
        self.assertEqual(review.dismissals("false_positive"), 3)

    # parsing, fail-closed
    def test_parse_ok(self):
        found, declined = review.parse_output(fenced(GOOD))
        self.assertEqual(len(found), 2)
        self.assertEqual(declined, ["generated code"])
        self.assertEqual(review.parse_output(json.dumps({"findings": []}))[0], [])

    def test_parse_fail_closed(self):
        for bad in ["no json here", "```json\n{broken\n```", fenced({"nofindings": 1}),
                    fenced({"findings": [{"file": "a", "text": "t", "severity": "huge", "confidence": 90}]}),
                    fenced({"findings": [{"file": "a", "text": "t", "severity": "minor"}]})]:
            with self.assertRaises(ValueError, msg=bad):
                review.parse_output(bad)

    # selection and dedupe
    def test_select_cut_cap_and_dedupe(self):
        found = [{"file": "a", "line": 1, "severity": "minor", "confidence": c, "text": f"t{i}", "scenario": "", "rule": ""}
                 for i, c in enumerate([95, 95, 95, 95, 95, 95, 79])]
        self.assertEqual(len(review.select(found, [])), 5)
        prev = [{"file": "a", "text": "T0!", "status": "dismissed"}]
        self.assertNotIn("t0", [f["text"] for f in review.select(found, prev)])
        fixed = [{"file": "a", "text": "t0", "status": "fixed"}]
        self.assertIn("t0", [f["text"] for f in review.select(found, fixed)])
        self.assertEqual(review.dedupe_key("a", "Hello,  World"), review.dedupe_key("a", "hello world"))

    # run and exit codes
    def test_run_blocker_exit_1_and_journal(self):
        self.assertEqual(self.run_review(GOOD), 1)
        ev = [e["event"] for e in review._all_events()]
        self.assertEqual(ev, ["review.started", "finding.reported", "review.finished"])
        self.assertEqual(len(review.findings(open_only=True)), 1)  # the 50-confidence one was cut
        self.assertEqual(len(list((Path(os.environ["REVIEW_DIR"]) / "runs").glob("*.md"))), 1)

    def test_run_second_pass_dedupes(self):
        self.run_review(GOOD)
        self.assertEqual(self.run_review(GOOD), 1)  # the open blocker still blocks
        self.assertEqual(sum(e["event"] == "finding.reported" for e in review._all_events()), 1)

    def test_run_clean_exit_0(self):
        self.assertEqual(self.run_review({"findings": []}), 0)

    def test_run_unparsable_exit_2(self):
        self.assertEqual(self.run_review(text="all good, no json"), 2)
        last = review._all_events()[-1]
        self.assertEqual(last["event"], "review.finished")
        self.assertIn("error", last["value"])

    def test_run_refuses_empty_diff_and_dirty_tree(self):
        git(self.repo, "checkout", "-q", "main")
        self.assertEqual(self.run_review({"findings": []}), 2)
        git(self.repo, "checkout", "-q", "feat")
        (self.repo / "app.py").write_text("dirty\n")
        self.assertEqual(self.run_review({"findings": []}), 2)
        self.assertEqual(review._all_events(), [])

    def test_prompt_has_rules_and_previous(self):
        prompt = review.build_prompt("DIFFTEXT", [{"status": "dismissed", "reason": "intended", "file": "a.py", "text": "old"}])
        for needle in ("DIFFTEXT", "HOUSE RULES", "uv PEP 723", "[dismissed/intended] a.py: old", "INTRODUCED"):
            self.assertIn(needle, prompt)

    def test_cli_main(self):
        self.assertEqual(review.main(["emit", "review.started", '{"text":"x"}', "--actor", "t"]), 0)
        self.assertEqual(review.main(["emit", "review.started", "{}", "--actor", "t"]), 2)
        self.assertEqual(review.main(["findings", "--open"]), 0)


if __name__ == "__main__":
    unittest.main()
