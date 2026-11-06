# /// script
# requires-python = ">=3.10"
# dependencies = ["starlette", "httpx"]
# ///
"""Tests of console_recorder.py: the reads and the three routes, on a temp recorder dir and invented lines.
Run: uv run --script test_console_recorder.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
import console_recorder as rec  # noqa: E402


def mk(i, **kw):
    base = {"at": f"20261106T1200{i:02d}.000Z", "url": f"http://127.0.0.1:5094/domain/d{i}", "domain": f"d{i}", "module": "Domain",
            "event": None, "widget": None, "width": 960, "height": 800, "errors": [], "shot": f"/x/shots/{i}.png"}
    base.update(kw)
    return base


def client():
    """The routes on a bare Starlette app, with a shim for the console's `rt` (query params become arguments)."""
    routes = []

    def rt(path):
        def deco(fn):
            async def endpoint(request):
                kw = {k: int(v) for k, v in request.query_params.items() if k == "n"}
                return fn(**kw)
            routes.append(Route(path, endpoint))
            return fn
        return deco

    rec.register(rt, lambda data, status=200: JSONResponse(data, status_code=status), base_url=lambda: "http://127.0.0.1:5094/")
    return TestClient(Starlette(routes=routes))


class RecorderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"DEV_CONSOLE_RECORDER_DIR": self.tmp.name})
        self.env.start()
        self.c = client()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, lines, raw=None):
        (self.dir / "events.jsonl").write_text(raw if raw is not None else "".join(json.dumps(x) + "\n" for x in lines))

    def test_now_is_the_last_line(self):
        self.write([mk(1), mk(2)])
        r = self.c.get("/agent/now")
        self.assertEqual((r.status_code, r.json()["domain"]), (200, "d2"))

    def test_now_without_a_file_is_404_with_a_message(self):
        r = self.c.get("/agent/now")
        self.assertEqual(r.status_code, 404)
        self.assertIn("no lines", r.json()["error"])

    def test_history_defaults_to_five_and_takes_n(self):
        self.write([mk(i) for i in range(1, 9)])
        self.assertEqual([x["domain"] for x in self.c.get("/agent/history").json()], ["d4", "d5", "d6", "d7", "d8"])
        self.assertEqual([x["domain"] for x in self.c.get("/agent/history?n=2").json()], ["d7", "d8"])
        self.assertEqual(len(self.c.get("/agent/history?n=99").json()), 8)  # capped at the ring size, never beyond the file
        self.assertEqual(len(self.c.get("/agent/history?n=0").json()), 1)

    def test_history_caps_at_twenty_and_skips_broken_lines(self):
        raw = "".join(json.dumps(mk(i % 60)) + "\n" for i in range(30)) + "not json\n[1]\n"
        self.write(None, raw=raw)
        self.assertEqual(len(self.c.get("/agent/history?n=50").json()), 18)  # the last 20 raw lines, 2 of them not objects
        self.assertEqual(self.c.get("/agent/history?n=1").json()[0]["domain"], "d29")

    def test_shot_from_the_app(self):
        self.write([mk(1)])

        def ask(timeout=15.0):  # the app appends a line
            with open(self.dir / "events.jsonl", "a") as f:
                f.write(json.dumps(mk(2)) + "\n")
            return True
        with mock.patch.object(rec, "app_running", return_value=True), mock.patch.object(rec, "ask_app_for_shot", ask):
            j = self.c.get("/agent/shot").json()
        self.assertEqual((j["source"], j["domain"]), ("app", "d2"))

    def test_shot_falls_back_to_headless_and_says_so(self):
        self.write([mk(1)])
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            shot = Path(cmd[cmd.index("--shot") + 1])
            shot.write_bytes(b"\x89PNG")
            return mock.Mock(stdout=json.dumps({"url": cmd[1], "errors": []}), returncode=0)
        with mock.patch.object(rec, "app_running", return_value=False), mock.patch.object(rec.subprocess, "run", fake_run):
            j = self.c.get("/agent/shot").json()
        self.assertEqual(j["source"], "headless")
        self.assertIn("headless", j["note"])
        self.assertEqual(seen["cmd"][1], "http://127.0.0.1:5094/domain/d1")  # the last known page
        self.assertTrue(Path(j["shot"]).exists() and Path(j["shot"]).parent == self.dir / "shots")
        self.assertEqual(len(rec.read_lines()), 1)  # the ring is untouched

    def test_headless_fallback_without_history_uses_the_consoles_own_url(self):
        def fake_run(cmd, **kw):
            Path(cmd[cmd.index("--shot") + 1]).write_bytes(b"x")
            return mock.Mock(stdout="{}", returncode=0)
        with mock.patch.object(rec, "app_running", return_value=False), mock.patch.object(rec.subprocess, "run", fake_run):
            j = self.c.get("/agent/shot").json()
        self.assertEqual(j["url"], "http://127.0.0.1:5094/")


if __name__ == "__main__":
    unittest.main()
