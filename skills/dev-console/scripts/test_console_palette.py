# /// script
# requires-python = ">=3.10"
# ///
"""The console home module (CONSOLE_HOME, the Kanban module) is in ⌘P from every page: D.modules of the web pages. Starts a real console on a test port with two projects, an empty registry and a
temp costs dir (never the owner's console or journal).
Run: uv run --script test_console_palette.py   (env DEVC_TEST_PORT, default 5098)"""
import json
import os
import re
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("DEVC_TEST_PORT", "5098"))
BASE = f"http://127.0.0.1:{PORT}"
HOME = {"name": "Kanban", "href": "/domain/kanban?tab=Kanban"}


def get(path: str) -> str:
    return urllib.request.urlopen(BASE + path, timeout=15).read().decode()


def modules(path: str) -> list[dict]:
    html = get(path)
    return json.loads(re.search(r'<script[^>]*id="data"[^>]*>(.*?)</script>', html, re.S).group(1))["modules"]


class HomeModuleInPalette(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "reg").mkdir()
        (tmp / "reg" / "registry").write_text("")
        env = {**os.environ, "DEV_CONSOLE_REGISTRY": str(tmp / "reg" / "registry"), "COSTS_DIR": str(tmp / "costs"),
               "DEV_CONSOLE_DB": str(tmp / "db" / "dev-console.sqlite")}  # never the owner's database
        kanban = HERE.parent.parent / "kanban" / "scripts" / "dev_console_project.py"
        cls.proc = subprocess.Popen(
            ["uv", "run", "--script", str(HERE / "dev-console.py"), "--project", str(HERE / "dev_console_project.py"),
             "--project", str(kanban), "--port", str(PORT)],
            cwd=str(tmp), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while True:  # the server answers when it is up; a dead process ends the wait
            if cls.proc.poll() is not None:
                raise RuntimeError("console exited before answering")
            try:
                get("/api/domains")
                break
            except OSError:
                pass

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=20)
        cls.tmp.cleanup()

    def test_modules_of_pages_without_tabs_lead_with_the_home(self):
        for page in ("/playground", "/agents", "/browser"):
            mods = modules(page)
            self.assertEqual(mods[0], HOME, page)
            self.assertEqual([m["name"] for m in mods].count("Kanban"), 1, page)

    def test_modules_of_another_domain_page_lead_with_the_home(self):
        mods = modules("/domain/dev-console")
        self.assertEqual(mods[0], HOME)
        self.assertEqual([m["name"] for m in mods].count("Kanban"), 1)

    def test_kanban_page_does_not_duplicate_the_home(self):
        mods = modules("/domain/kanban")
        self.assertEqual([m for m in mods if m["name"] == "Kanban"], [{"name": "Kanban", "href": None}])

    def test_old_tab_name_still_opens_the_board(self):
        data = json.loads(re.search(r'<script[^>]*id="data"[^>]*>(.*?)</script>', get("/domain/kanban?tab=Quadro"), re.S).group(1))
        self.assertEqual(data["module_aliases"], {"Quadro": "Kanban"})
        self.assertIn("Kanban", data["tabs"])
        self.assertEqual(data["module_widgets"]["Kanban"], ["card.created", "Board"])


if __name__ == "__main__":
    unittest.main()
