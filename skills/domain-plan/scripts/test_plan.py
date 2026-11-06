#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""domain-plan tests: every plan lives in a temp dir."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan as P  # noqa: E402


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / "events.py").write_text('EVENTS = {"req": {"send": "sent", "fix": "fixed"}}\n')

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = P.main([*args])
        return code, out.getvalue()

    def cli(self, cmd, slug, *args):
        return self.run_cli(cmd, slug, "--repo", str(self.repo), *args)

    def start(self):
        return self.cli("start", "demo", "--events-file", "events.py")

    def test_start_writes_the_jsonl_once(self):
        self.assertEqual(self.start()[0], 0)
        self.assertIn("already open", self.start()[1])
        lines = (self.repo / ".plan" / "demo.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(x)["event"] for x in lines], ["plan.started"])

    def test_bad_slug_and_bad_event_name(self):
        self.assertEqual(self.run_cli("start", "Bad Slug", "--repo", str(self.repo))[0], 1)
        self.start()
        self.assertEqual(self.cli("add", "demo", "--kind", "event", "--name", "NoDot")[0], 1)

    def test_drift_three_groups(self):
        self.start()
        self.cli("add", "demo", "--kind", "event", "--name", "req.sent")        # draft, the code has it: built
        self.cli("add", "demo", "--kind", "event", "--name", "req.returned")    # draft, not in code: to build
        self.cli("add", "demo", "--kind", "screen", "--name", "inbox", "--event", "req.returned", "--file", "inbox.html")
        code, out = self.cli("drift", "demo", "--json")
        d = json.loads(out)
        self.assertEqual([i["name"] for i in d["built"]], ["req.sent"])
        self.assertEqual(sorted(i["name"] for i in d["to_build"]), ["inbox", "req.returned"])
        self.assertEqual([i["name"] for i in d["unplanned"]], ["req.fixed"])

    def test_screen_file_built_when_it_exists(self):
        self.start()
        self.cli("add", "demo", "--kind", "screen", "--name", "inbox", "--file", "inbox.html")
        (self.repo / "inbox.html").write_text("<p>x</p>")
        d = json.loads(self.cli("drift", "demo", "--json")[1])
        self.assertEqual([i["name"] for i in d["built"]], ["inbox"])

    def test_mark_turns_built_into_real(self):
        self.start()
        self.cli("add", "demo", "--kind", "event", "--name", "req.sent")
        self.cli("drift", "demo", "--mark")
        st = P.project(P.read_events(self.repo / ".plan" / "demo.jsonl"))
        self.assertEqual(st["elements"][("event", "req.sent")]["state"], "real")

    def test_real_element_that_left_the_code_is_lost(self):
        self.start()
        self.cli("add", "demo", "--kind", "event", "--name", "req.gone", "--state", "real")
        d = json.loads(self.cli("drift", "demo", "--json")[1])
        self.assertEqual([i["name"] for i in d["lost"]], ["req.gone"])

    def test_documents_carry_decisions_sources_questions(self):
        self.start()
        self.cli("add", "demo", "--kind", "document", "--name", "goal", "--question", "which one?",
                 "--decision", "Decidi X porque Y", "--source", "wiki")
        d = json.loads(self.cli("drift", "demo", "--json")[1])
        self.assertEqual(d["documents"][0]["questions"], ["which one?"])
        self.assertEqual((d["to_build"], d["built"]), ([], []))

    def test_delete_removes_the_element_and_hand_edits_fold(self):
        self.start()
        self.cli("add", "demo", "--kind", "event", "--name", "req.returned")
        self.cli("add", "demo", "--kind", "event", "--name", "req.returned", "--delete")
        self.assertNotIn(("event", "req.returned"), P.project(P.read_events(self.repo / ".plan" / "demo.jsonl"))["elements"])
        path = self.repo / ".plan" / "demo.jsonl"   # a line written by hand counts as any other
        with path.open("a") as f:
            f.write(json.dumps({"id": "h", "event": "element.updated", "at": "x", "actor": "owner",
                                "value": {"kind": "event", "name": "req.handmade", "state": "draft"}}) + "\n")
        self.assertIn(("event", "req.handmade"), P.project(P.read_events(path))["elements"])

    def test_detailed_exitcode_and_confirm(self):
        self.start()
        self.cli("add", "demo", "--kind", "event", "--name", "req.returned")
        self.assertEqual(self.cli("drift", "demo", "--detailed-exitcode")[0], 2)
        self.cli("confirm", "demo")
        self.assertTrue(P.project(P.read_events(self.repo / ".plan" / "demo.jsonl"))["confirmed"])

    def test_without_events_file_only_screens_are_read(self):
        self.cli("start", "bare")
        out = self.cli("drift", "bare")[1]
        self.assertIn("sem leitor de EVENTS", out)


class ConsoleSideTest(unittest.TestCase):
    REAL = ('"""doc."""\nEVENTS = {\n    "req": {\n        # real\n        "send": "sent",\n    },\n}\n\n\ndef _project(e):\n    return None\n')

    def plan(self, t):
        (Path(t) / "events.py").write_text(self.REAL)
        self.cli(t, "start", "d", "--events-file", "events.py", "--console-source", "console_events.py")
        return Path(t) / "console_events.py"

    def cli(self, t, *args):
        with redirect_stdout(io.StringIO()):
            return P.main([args[0], args[1], "--repo", t, *args[2:]])

    def test_drafts_are_written_into_the_console_source_and_keep_the_code(self):
        with tempfile.TemporaryDirectory() as t:
            src = self.plan(t)
            self.cli(t, "add", "d", "--kind", "event", "--name", "req.returned", "--command", "return")
            self.cli(t, "add", "d", "--kind", "event", "--name", "stage.routed")
            text = src.read_text()
            ns = {}
            exec(compile(text, "x", "exec"), ns)
            self.assertEqual(ns["EVENTS"], {"req": {"send": "sent", "return": "returned"}, "stage": {"routed": "routed"}})
            self.assertIn("# real", text)
            self.assertIn("rascunho: só no grafo", text)
            self.assertIn("def _project", text)

    def test_a_built_draft_is_not_written_twice(self):
        with tempfile.TemporaryDirectory() as t:
            src = self.plan(t)
            self.cli(t, "add", "d", "--kind", "event", "--name", "req.sent")
            self.assertEqual(src.read_text(), self.REAL)
            self.assertEqual(P.registry(Path(t) / "events.py"), ["req.sent"])   # drift reads the real file, not the merged one

    def test_a_hand_edited_name_cannot_inject_into_the_source(self):
        with tempfile.TemporaryDirectory() as t:
            self.plan(t)
            self.assertEqual(self.cli(t, "add", "d", "--kind", "event", "--name", "req.ok", "--command", 'x": "y", #'), 1)
            f = Path(t) / ".plan" / "d.jsonl"
            P.append(f, "element.updated", {"kind": "event", "name": 'req.a"b', "state": "draft"})
            with self.assertRaises(ValueError):
                P.render_source((Path(t) / "events.py").read_text(), P.project(P.read_events(f)))

    def test_edges(self):
        import dev_console_plan as C
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / ".plan" / "d.jsonl"
            P.append(f, "plan.started", {"slug": "d", "domain": "d", "events_file": None})
            P.append(f, "element.updated", {"kind": "event", "name": "req.returned", "after": "req.sent", "state": "draft"})
            self.assertEqual(C.with_edges({"req.sent": []}, f), {"req.sent": ["req.returned"]})


if __name__ == "__main__":
    unittest.main()
