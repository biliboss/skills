"""Tests for devc.py: a fake console (http.server, in-process, random port) and stub scripts in a temp dir.

Run: python3 -m unittest skills/dev-console/scripts/test_devc.py
"""
import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import devc  # noqa: E402

STATE = {
    "name": "Demo",
    "model": {
        "lifecycle": {"task": ["explained", "executed"], "learning": ["recorded"]},
        "next": {"task.explained": ["task.executed"], "task.executed": ["learning.recorded"]},
        "edge_cmd": {},
        "commands": {"task.executed": "execute"},
        "stage_order": [],
    },
    "entities": {"task": "Task"},
    "journal_types": {"task.explained": 1, "task.executed": 1},
    "events": [
        {"id": "e1", "event": "task.explained", "at": "2026-11-06T09:00:01Z", "actor": "gabriel", "task_id": "abcdef123456"},
        {"id": "e2", "event": "task.executed", "at": "2026-11-06T09:00:05Z", "actor": "bili", "task_id": "abcdef123456"},
    ],
}


class Fake(BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):
        path = self.path.split("?")[0]
        hit = Fake.routes.get(path)
        code, body = hit if hit else (404, {"error": "nope"})
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        pass


def run(*argv, scripts=None):
    """(exit code, stdout, stderr) of devc.main."""
    out, err = io.StringIO(), io.StringIO()
    old = devc.HERE
    if scripts:
        devc.HERE = Path(scripts)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = devc.main(list(argv))
    finally:
        devc.HERE = old
    return code, out.getvalue(), err.getvalue()


class DevcTest(unittest.TestCase):
    def setUp(self):
        Fake.routes = {
            "/api/domains": (200, [{"slug": "demo", "name": "Demo", "path": "/x", "origin": "--project"}]),
            "/domain/demo/state.json": (200, STATE),
        }
        self.srv = HTTPServer(("127.0.0.1", 0), Fake)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.05), daemon=True)
        self.thread.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.scripts = Path(self.tmp.name)
        for name in ("console.sh", "agent.sh", "window.sh", "check.sh"):  # stubs: echo their arguments
            p = self.scripts / name
            p.write_text(f'#!/bin/bash\nif [ "$1" = shot ]; then echo "shot    /tmp/x.png"; exit 0; fi\necho "{name} $*"\n')
            p.chmod(p.stat().st_mode | stat.S_IEXEC)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(5)
        self.tmp.cleanup()

    def p(self):
        return ["--port", str(self.port)]

    def test_domains_text_and_json(self):
        code, out, _ = run(*self.p(), "domains")
        self.assertEqual(code, 0)
        self.assertIn("demo", out)
        self.assertIn("--project", out)
        code, out, _ = run("domains", "--json", *self.p())
        self.assertEqual(json.loads(out)[0]["slug"], "demo")

    def test_show_text(self):
        code, out, _ = run(*self.p(), "show", "demo")
        self.assertEqual(code, 0)
        self.assertIn("task: explained → executed", out)
        self.assertIn("task.explained → task.executed", out)
        self.assertIn("(execute)", out)
        self.assertLess(out.index("09:00:01"), out.index("09:00:05"))  # journal order kept
        self.assertRegex(out, r"\*\| 09:00:01|\|\* 09:00:01|\* 09:00:01")

    def test_show_json(self):
        code, out, _ = run(*self.p(), "--json", "show", "demo")
        d = json.loads(out)
        self.assertEqual(d["lanes"]["task"], ["explained", "executed"])
        self.assertEqual(d["transitions"][0], {"from": "task.explained", "to": "task.executed", "command": "execute"})
        self.assertEqual(len(d["events"]), 2)

    def test_show_unknown_domain(self):
        code, _, err = run(*self.p(), "show", "zzz")
        self.assertEqual(code, 1)
        self.assertIn("'zzz' on port", err)
        self.assertIn("nope", err)

    def test_nothing_answers(self):
        self.srv.shutdown()
        self.srv.server_close()
        code, _, err = run(*self.p(), "domains")
        self.assertEqual(code, 1)
        self.assertIn("nothing answers", err)
        self.srv = HTTPServer(("127.0.0.1", 0), Fake)  # so tearDown has something to close
        self.thread = threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.05), daemon=True)
        self.thread.start()

    def test_events_tail_n(self):
        code, out, _ = run(*self.p(), "events", "demo", "-n", "1")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("task.executed", out)

    def test_events_follow_prints_only_new(self):
        more = dict(STATE, events=STATE["events"] + [{"id": "e3", "event": "task.verified", "at": "2026-11-06T09:00:09Z", "actor": "x"}])

        def grow():  # the journal grows while following
            Fake.routes["/domain/demo/state.json"] = (200, more)

        threading.Timer(0.3, grow).start()
        code, out, _ = run(*self.p(), "events", "demo", "--tail", "--max-polls", "2")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("task.verified", lines[-1])

    def test_events_task_param_and_bad_port(self):
        Fake.routes["/domain/demo/state.json"] = (200, STATE)
        self.assertEqual(run(*self.p(), "events", "demo", "--task", "abc", "-n", "1")[0], 0)
        self.assertEqual(run("--port=abc", "domains")[0], 2)

    def test_follow_with_n_does_not_replay_older(self):
        more = dict(STATE, events=STATE["events"] + [{"id": "e3", "event": "task.verified", "at": "2026-11-06T09:00:09Z", "actor": "x"}])
        threading.Timer(0.3, lambda: Fake.routes.__setitem__("/domain/demo/state.json", (200, more))).start()
        _, out, _ = run(*self.p(), "events", "demo", "--tail", "-n", "1", "--max-polls", "2")
        self.assertEqual(len(out.strip().splitlines()), 2)  # the last one, then only e3

    def test_events_json_lines(self):
        _, out, _ = run(*self.p(), "--json", "events", "demo")
        self.assertEqual([json.loads(l)["id"] for l in out.splitlines()], ["e1", "e2"])

    def test_focus_without_route(self):
        code, out, _ = run(*self.p(), "focus")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "sem foco ainda")

    def test_focus_with_route(self):
        Fake.routes["/agent/focus"] = (200, {"domain": "demo", "widget": "w1"})
        _, out, _ = run(*self.p(), "focus")
        self.assertIn("demo", out)
        _, out, _ = run(*self.p(), "--json", "focus")
        self.assertEqual(json.loads(out)["widget"], "w1")

    def test_now_and_history(self):
        line = {"at": "T", "url": "http://x/", "domain": "demo", "module": "M", "errors": [], "shot": "/p.png"}
        Fake.routes["/agent/now"] = (200, line)
        Fake.routes["/agent/history"] = (200, [line, line])
        _, out, _ = run(*self.p(), "now")
        self.assertIn("domain  demo", out)
        _, out, _ = run(*self.p(), "--json", "history", "2")
        self.assertEqual(len(json.loads(out)), 2)

    def test_now_empty_is_an_error(self):
        Fake.routes["/agent/now"] = (404, {"error": "no lines yet"})
        code, _, err = run(*self.p(), "now")
        self.assertEqual(code, 1)
        self.assertIn("no lines yet", err)

    def test_history_bounds(self):
        self.assertEqual(run(*self.p(), "history", "99")[0], 2)

    def test_open_marks_agent_and_builds_url(self):
        _, out, _ = run(*self.p(), "open", "demo", "--ev", "e1", "--w", "W", scripts=self.scripts)
        self.assertIn(f"agent.sh open http://127.0.0.1:{self.port}/domain/demo?ev=e1&w=W&agent=1", out)

    def test_open_url(self):
        _, out, _ = run(*self.p(), "open", "http://h/p?a=1", scripts=self.scripts)
        self.assertIn("http://h/p?a=1&agent=1", out)

    def test_shot_prints_path(self):
        code, out, _ = run(*self.p(), "shot", scripts=self.scripts)
        self.assertEqual((code, out.strip()), (0, "/tmp/x.png"))

    def test_eval_start_stop_check_passthrough(self):
        _, out, _ = run("eval", "1+1", scripts=self.scripts)
        self.assertEqual(out.strip(), "agent.sh eval 1+1")
        for cmd in (["start", "5060", "--owner", "me"], ["stop", "5060"], ["check", "http://x"]):
            self.assertEqual(run(*cmd, scripts=self.scripts)[0], 0)  # passthrough writes to fd 1 itself

    def test_start_adds_owner(self):
        calls = []
        orig = devc.run_script
        devc.run_script = lambda n, a, passthrough=False: calls.append((n, a)) or type("R", (), {"returncode": 0})()
        try:
            os.environ["DEVC_OWNER"] = "hacker"
            run("start", "5060")
        finally:
            devc.run_script = orig
            os.environ.pop("DEVC_OWNER", None)
        self.assertEqual(calls, [("console.sh", ["start", "5060", "--owner", "hacker"])])

    def test_list_filters_port(self):
        (self.scripts / "console.sh").write_text("#!/bin/bash\nprintf ':5057\\n  owner: a\\n:5058\\n  owner: b\\n'\n")
        _, out, _ = run("list", "5058", scripts=self.scripts)
        self.assertIn("owner: b", out)
        self.assertNotIn("owner: a", out)

    def test_install_symlinks(self):
        (self.scripts / "devc").write_text("#!/bin/bash\n")
        bin_dir = self.scripts / "bin"
        os.environ["DEVC_BIN_DIR"] = str(bin_dir)
        try:
            code, _, _ = run("install", scripts=self.scripts)
            self.assertEqual(code, 0)
            self.assertTrue((bin_dir / "devc").is_symlink())
            self.assertEqual(run("install", scripts=self.scripts)[0], 0)  # idempotent
        finally:
            os.environ.pop("DEVC_BIN_DIR", None)

    def test_unknown_command_and_help(self):
        self.assertEqual(run("nope")[0], 2)
        code, out, _ = run()
        self.assertEqual(code, 0)
        self.assertIn("usage: devc", out)


KANBAN_SH = Path(__file__).resolve().parent.parent.parent / "kanban" / "scripts" / "kanban.sh"


class DevcKanbanTest(unittest.TestCase):
    """devc board / delegated / done against the real kanban.sh, one temp KANBAN_DIR per test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"KANBAN_DIR": self.tmp.name, "DEVC_KANBAN_SH": str(KANBAN_SH)}
        self.old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def cards(self):
        return [r["card"] for r in json.loads(subprocess_out("list"))]

    def test_delegated_creates_in_downstream_and_prints_id(self):
        code, out, _ = run("delegated", "Fix the login", "--domain", "via")
        self.assertEqual(code, 0)
        card = out.strip()
        c = [c for c in self.cards() if c["id"] == card][0]
        self.assertEqual((c["stage"], c["title"], c["domain"]), ("Downstream", "Fix the login", "via"))

    def test_delegated_json_and_actor(self):
        code, out, _ = run("delegated", "Goal", "--domain", "via", "--by", "bili-local", "--json")
        d = json.loads(out)
        self.assertEqual((d["stage"], d["created"]), ("Downstream", True))
        evs = [json.loads(l) for l in (Path(self.tmp.name) / "events.jsonl").read_text().splitlines()]
        self.assertEqual(evs[-1]["actor"], "bili-local")

    def test_delegated_idempotent_while_open(self):
        _, a, _ = run("delegated", "Same", "--domain", "via")
        _, b, _ = run("delegated", "Same", "--domain", "via")
        self.assertEqual(a, b)
        self.assertEqual(len(self.cards()), 1)
        _, other, _ = run("delegated", "Same", "--domain", "blog")  # another domain: another card
        self.assertNotEqual(a, other)
        run("done", a.strip())
        _, again, _ = run("delegated", "Same", "--domain", "via")  # closed: a new one
        self.assertNotEqual(a, again)

    def test_delegated_parent_prefix_and_trim(self):
        pid = json.loads(run("delegated", "Via Blog", "--domain", "via", "--json")[1])["card"]
        _, out, _ = run("delegated", "Write the post", "--domain", "via", "--parent", pid[:4])
        self.assertEqual([c for c in self.cards() if c["id"] == out.strip()][0]["title"], "Via Blog · Write the post")
        _, out, _ = run("delegated", "x" * 200, "--domain", "via")
        t = [c for c in self.cards() if c["id"] == out.strip()][0]["title"]
        self.assertEqual(len(t), 80)
        self.assertTrue(t.endswith("…"))

    def test_delegated_errors(self):
        self.assertEqual(run("delegated", "Goal")[0], 2)  # no --domain
        code, _, err = run("delegated", "Goal", "--domain", "via", "--parent", "nope")
        self.assertEqual(code, 1)
        self.assertIn("parent", err)

    def test_done_moves_to_feito(self):
        card = run("delegated", "Job", "--domain", "via")[1].strip()
        code, out, _ = run("done", card, "--note", "PR #1")
        self.assertEqual(code, 0)
        self.assertIn("Feito", out)
        self.assertIn("PR #1", out)
        self.assertEqual([c for c in self.cards() if c["id"] == card][0]["stage"], "Feito")
        self.assertEqual(run("done", "nosuchcard")[0], 1)

    def test_board_passthrough(self):
        run("delegated", "Job", "--domain", "via")
        code, text = board_run("list")
        self.assertEqual(code, 0)
        self.assertIn("Job", text)
        self.assertEqual(board_run("move", "Job", "Feito")[0], 0)


def subprocess_out(*args):
    import subprocess
    return subprocess.run([str(KANBAN_SH), *args, "--json"], capture_output=True, text=True, check=True).stdout


def board_run(*args):
    """devc board writes through the real fd (subprocess passthrough): run devc as a process and capture it."""
    import subprocess
    p = subprocess.run([sys.executable, str(Path(devc.__file__)), "board", *args], capture_output=True, text=True)
    return p.returncode, p.stdout


if __name__ == "__main__":
    unittest.main()
