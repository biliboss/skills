#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6,<7", "jsonschema>=4,<5"]
# ///
"""Isolated acceptance tests: actual failures, proof lifecycle and Git selection."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

spec = importlib.util.spec_from_file_location("contracts", Path(__file__).with_name("contracts.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.state = self.base / "state"
        self.c = {"id": "ready", "kind": "fast", "expected": "artifact exists", "red": "artifact is absent", "remedy": "create artifact", "file": "artifact"}
        self.write()

    def write(self, checks=None, **cap):
        self.data = {"capabilities": {"feature": {"intent": "Deliver artifact", "checks": checks or [self.c], "keep": ["ready"], "success": ["keep"], **cap}}}
        (self.root / ".doctor.yaml").write_text(yaml.safe_dump(self.data))

    def run_doctor(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            previous = sys.argv
            sys.argv = ["doctor", "--root", str(self.root), "--state-dir", str(self.state), "--json", *args]
            try:
                rc = m.main()
            finally:
                sys.argv = previous
        return rc, json.loads(out.getvalue()) if out.getvalue() else err.getvalue()

    def proof(self):
        rc, report = self.run_doctor("--record-red", "ready")
        self.assertEqual(rc, 1)
        self.assertEqual(report["results"][0]["status"], "FAIL")
        sha = report["results"][0]["red_observed_sha256"]
        return sha

    def confirm(self, sha):
        return self.run_doctor("--record-red", "ready", "--confirm-red", self.c["red"], "--confirm-observed", sha)

    def test_real_red_fix_green_invalidation(self):
        sha = self.proof()
        (self.root / "artifact").write_text("delivered")
        self.assertEqual(self.run_doctor()[1]["results"][0]["status"], "PEND")
        rc, report = self.confirm(sha)
        self.assertEqual(rc, 0)
        self.assertTrue(report["capabilities"][0]["success"])
        self.c["expected"] = "new expectation"
        self.write()
        self.assertEqual(self.run_doctor()[1]["results"][0]["status"], "PEND")

    def test_confirmation_needs_output_and_reason(self):
        sha = self.proof()
        self.assertEqual(self.confirm("wrong")[0], 2)
        self.assertEqual(self.run_doctor("--record-red", "ready", "--confirm-red", "wrong", "--confirm-observed", sha)[0], 2)

    def test_validate_every_contract_before_side_effects(self):
        marker = self.root / "executed"
        c = {**self.c, "run": {"command": [sys.executable, "-c", "open('executed','w').write('bad')"], "why_script": "test guard"}}
        del c["file"]
        self.write([c])
        nested = self.root / "other"
        nested.mkdir()
        (nested / ".doctor.yaml").write_text("invalid: [")
        self.assertEqual(self.run_doctor()[0], 2)
        self.assertFalse(marker.exists())

    def test_invalid_contracts(self):
        variants = [([self.c, self.c], {}), ([{**self.c, "cli": {"command": ["true"]}}], {}), ([{**self.c, "kind": "implicit"}], {}), ([self.c], {"success": ["missing"]}), ([self.c], {"keep": ["missing"]})]
        for checks, cap in variants:
            with self.subTest(checks=checks, cap=cap):
                self.write(checks, **cap)
                self.assertEqual(self.run_doctor()[0], 2)
        (self.root / ".doctor.yaml").write_text("capabilities: {}\ncapabilities: {}\n")
        self.assertEqual(self.run_doctor()[0], 2)

    def test_script_hash_invalidation(self):
        script = self.root / "probe.py"
        script.write_text("import pathlib; raise SystemExit(not pathlib.Path('artifact').exists())")
        self.c.pop("file")
        self.c["run"] = {"command": [sys.executable, "probe.py"], "why_script": "probe lifecycle"}
        self.write()
        sha = self.proof()
        (self.root / "artifact").touch()
        self.assertEqual(self.confirm(sha)[0], 0)
        script.write_text(script.read_text() + "\n# modified\n")
        self.assertEqual(self.run_doctor()[1]["results"][0]["status"], "PEND")

    def test_timeout_and_infrastructure_do_not_record_red(self):
        self.c.pop("file")
        self.c["cli"] = {"command": [sys.executable, "-c", "import time;time.sleep(2)"]}
        self.c["timeout"] = 0.03
        self.write()
        self.assertEqual(self.run_doctor("--record-red", "ready")[0], 3)
        self.assertFalse(list(self.state.rglob("*.json")))
        self.c["cli"]["command"] = ["/absent-doctor-executable"]
        self.write()
        rc, report = self.run_doctor("--record-red", "ready")
        self.assertEqual(rc, 1)
        self.assertEqual(report["results"][0]["failure_type"], "infrastructure")
        self.assertFalse(list(self.state.rglob("*.json")))

    def test_partial_and_selection(self):
        runtime = {**self.c, "id": "live", "kind": "runtime"}
        journey = {**self.c, "id": "user", "kind": "journey"}
        self.write([self.c, runtime, journey])
        self.assertFalse(self.run_doctor()[1]["capabilities"][0]["complete"])
        self.assertEqual([x["id"] for x in self.run_doctor("runtime")[1]["results"]], ["live"])
        self.assertEqual([x["id"] for x in self.run_doctor("journey")[1]["results"]], ["user"])
        self.assertEqual(len(self.run_doctor("--all")[1]["results"]), 3)
        self.assertEqual(self.run_doctor("--capability", "absent")[0], 2)

    def test_adapters_pending_and_safety(self):
        self.c.pop("file")
        self.c["agent"] = {"task": "exercise journey"}
        self.write()
        rc, report = self.run_doctor()
        self.assertEqual(rc, 1)
        self.assertEqual(report["results"][0]["status"], "PEND")
        self.c.pop("agent")
        self.c["http"] = {"url": "https://example.invalid/"}
        self.write()
        self.assertEqual(self.run_doctor()[0], 2)
        self.c.pop("http")
        self.c["sql"] = {"query": "SELECT 1", "read_only": False}
        self.write()
        self.assertEqual(self.run_doctor()[0], 2)

    def test_missing_interpreter_script_is_infrastructure(self):
        self.c.pop("file")
        self.c["run"] = {"command": [sys.executable, "absent.py"], "why_script": "exercise error classification"}
        self.write()
        rc, report = self.run_doctor("--record-red", "ready")
        self.assertEqual(rc, 1)
        self.assertEqual(report["results"][0]["failure_type"], "infrastructure")
        self.assertFalse(list(self.state.rglob("*.json")))

    def test_http_timeout_and_adapter_hash(self):
        c = {**self.c, "http": {"url": "http://localhost/"}}
        del c["file"]
        with patch.object(m.urllib.request, "build_opener", side_effect=TimeoutError("timed out")):
            self.assertEqual(m.execute(self.root / ".doctor.yaml", c, {})[2], "timeout")
        adapter = self.root / "adapter.py"
        adapter.write_text("print('one')")
        config = {"adapters": {"agent": [sys.executable, "adapter.py"]}}
        before = m.digest(self.root / ".doctor.yaml", self.c, config)
        adapter.write_text("print('two')")
        self.assertNotEqual(before, m.digest(self.root / ".doctor.yaml", self.c, config))

    def test_primitive_grep_and_schema(self):
        (self.root / "artifact").write_text('{"name": 42}')
        self.c.pop("file")
        self.c["grep"] = {"path": "artifact", "pattern": "missing"}
        self.write()
        self.assertEqual(self.run_doctor()[1]["results"][0]["status"], "FAIL")
        self.c.pop("grep")
        self.c["schema"] = {"path": "artifact", "schema": {"type": "object", "properties": {"name": {"type": "string"}}}}
        self.write()
        self.assertEqual(self.run_doctor()[1]["results"][0]["status"], "FAIL")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_changed_untracked_rename_and_nearest_contract(self):
        self.git("init", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        app = self.root / "app"
        app.mkdir()
        (app / ".doctor.yaml").write_text((self.root / ".doctor.yaml").read_text())
        (app / "old").write_text("content")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("mv", "app/old", "renamed")
        (app / "new").touch()
        rc, report = self.run_doctor("--changed", "--base", "HEAD")
        self.assertEqual(rc, 1)
        self.assertEqual(len(report["capabilities"]), 2)
        self.assertIn("app/old", m.changed_files(self.root, "HEAD"))
        self.assertIn("renamed", m.changed_files(self.root, "HEAD"))
        (self.root / ".doctor.yaml").unlink()
        rc, report = self.run_doctor("--changed")
        self.assertIn("renamed", report["uncovered"])

if __name__ == "__main__":
    unittest.main()
