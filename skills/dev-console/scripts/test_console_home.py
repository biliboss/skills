# /// script
# requires-python = ">=3.10"
# dependencies = ["watchfiles>=0.21", "python-fasthtml>=0.14"]
# ///
"""The Home as a SQLite table: the `home` table starts with only the logo, show/rm/clear, position and parent, the
`widgets` catalogue mirrors the loaded projects, and a write from another process (the owner in a SQLite app) reaches
the SSE stream. Temp database every time (DEV_CONSOLE_DB), never the owner's.
Run: uv run --script test_console_home.py   (env DEVC_TEST_PORT, default 5097, for the live console test)"""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import console_home as HM  # noqa: E402
import console_store as ST  # noqa: E402

PORT = int(os.environ.get("DEVC_TEST_PORT", "5097"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "db" / "dev-console.sqlite"
        self._env = {k: os.environ.get(k) for k in ("DEV_CONSOLE_DB", "DEV_CONSOLE_HOME_DIR")}
        os.environ["DEV_CONSOLE_DB"] = str(self.db)
        os.environ["DEV_CONSOLE_HOME_DIR"] = str(Path(self.tmp.name) / "home")
        self.addCleanup(self.restore)

    def restore(self):
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.tmp.cleanup()

    def ids(self):
        return [w["id"] for w in ST.list_home()]


class Home(Base):
    def test_first_creation_seeds_exactly_the_logo(self):
        HM.init()
        rows = ST.list_home()
        self.assertEqual([(r["id"], r["widget_id"], r["source"], r["position"]) for r in rows], [("logo", ST.LOGO_ID, "widget", 0)])
        self.assertFalse(rows[0]["chrome"])
        self.assertEqual(rows[0]["src"], "/domain/dev-console/w/_/domain.updated/Logo")
        HM.init()  # again: still one row
        self.assertEqual(self.ids(), ["logo"])
        self.assertEqual(sqlite3.connect(self.db).execute("PRAGMA journal_mode").fetchone()[0], "wal")

    def test_show_replace_rm_and_clear(self):
        HM.init()
        a = HM.show({"id": "a", "source": "html", "content": "<p>1</p>", "span": 2, "height": 200}, "bili")
        HM.show({"id": "b", "source": "url", "content": "http://x"}, "bili")
        self.assertEqual(self.ids(), ["logo", "a", "b"])
        self.assertEqual((a["actor"], a["span"], a["height"], a["position"]), ("bili", 2, 200, 1))
        again = HM.show({"id": "a", "source": "html", "content": "<p>2</p>"}, "other")  # same id = in place
        self.assertEqual((again["content"], again["position"], again["span"], again["created_at"]), ("<p>2</p>", 1, 2, a["created_at"]))
        self.assertEqual(self.ids(), ["logo", "a", "b"])
        self.assertTrue(HM.remove("a"))
        self.assertFalse(HM.remove("nope"))
        self.assertEqual(self.ids(), ["logo", "b"])
        HM.clear("bili")
        self.assertEqual(self.ids(), ["logo"])  # the initial state: only the logo

    def test_widget_source_and_validation(self):
        HM.init()
        r = HM.show({"id": "k", "source": "widget", "widget_id": "kanban/card.created/Board", "task": "T 1"})
        self.assertEqual(ST.list_home()[-1]["src"], "/domain/kanban/w/T%201/card.created/Board?task=T%201")
        self.assertIsNone(r["content"])
        old = HM.show({"id": "o", "kind": "widget", "content": "/domain/kanban/w/_/card.created/Board"})  # an older devc
        self.assertEqual((old["source"], old["widget_id"]), ("widget", "kanban/card.created/Board"))
        for bad in ({"id": "x", "source": "url", "content": "javascript:alert(1)"}, {"id": "x", "source": "url", "content": "//evil.example"},
                    {"id": "x"}, {"id": "x", "source": "html"}, {"id": "x", "source": "widget"}, {"source": "url", "content": "u"}):
            with self.assertRaises(ValueError):
                HM.show(bad)

    def test_position_and_parent(self):
        HM.init()
        HM.show({"id": "a", "source": "html", "content": "a"})
        HM.show({"id": "b", "source": "html", "content": "b", "position": 0})
        HM.show({"id": "c", "source": "html", "content": "c", "parent_id": "a"})
        self.assertEqual(self.ids(), ["logo", "b", "a", "c"])  # grid order = position
        rows = {r["id"]: r for r in ST.list_home()}
        self.assertEqual(rows["c"]["parent_id"], "a")
        HM.show({"id": "a", "source": "html", "content": "a", "position": 9})  # reorder in place
        self.assertEqual(self.ids()[-1], "a")
        # composition: removing the container removes what is inside it
        HM.remove("a")
        self.assertNotIn("c", self.ids())
        # a hand edit with a missing parent or a loop falls back to the top
        db = sqlite3.connect(self.db)
        HM.show({"id": "p", "source": "html", "content": "p"})
        HM.show({"id": "q", "source": "html", "content": "q", "parent_id": "p"})
        db.execute("UPDATE home SET parent_id='ghost' WHERE id='b'")
        db.execute("UPDATE home SET parent_id='q' WHERE id='p'")
        db.commit()
        db.close()
        rows = {r["id"]: r for r in ST.list_home()}
        self.assertIsNone(rows["b"]["parent_id"])
        self.assertEqual((rows["p"]["parent_id"], rows["q"]["parent_id"]), (None, "p"))  # the loop is cut
        with self.assertRaises(ValueError):
            HM.show({"id": "z", "source": "html", "content": "z", "parent_id": "z"})

    def test_old_journal_migrates_once_and_stays_untouched(self):
        j = Path(self.tmp.name) / "home" / "events.jsonl"
        j.parent.mkdir()
        lines = [
            {"id": "1", "event": "home.widget.shown", "at": "2026-01-01T10:00:00-0300", "actor": "bili",
             "value": {"id": "keep", "kind": "html", "content": "<b>x</b>", "title": "Keep", "span": 2}},
            {"id": "2", "event": "home.widget.shown", "at": "2026-01-01T10:00:01-0300", "actor": "bili",
             "value": {"id": "k", "kind": "widget", "content": "/domain/kanban/w/_/card.created/Board"}},
            {"id": "3", "event": "home.widget.shown", "at": "2026-01-01T10:00:02-0300", "actor": "bili",
             "value": {"id": "gone", "kind": "url", "content": "http://x"}},
            {"id": "4", "event": "home.widget.removed", "at": "2026-01-01T10:00:03-0300", "actor": "bili", "value": {"id": "gone"}},
        ]
        text = "".join(json.dumps(x) + "\n" for x in lines)
        j.write_text(text)
        HM.init()
        self.assertEqual(self.ids(), ["logo", "keep", "k"])
        rows = {r["id"]: r for r in ST.list_home()}
        self.assertEqual((rows["keep"]["span"], rows["keep"]["actor"], rows["keep"]["title"]), (2, "bili", "Keep"))
        self.assertEqual(rows["k"]["widget_id"], "kanban/card.created/Board")
        HM.clear()
        HM.init()  # the table exists: the journal is not read again
        self.assertEqual(self.ids(), ["logo"])
        self.assertEqual(j.read_text(), text)


def fake_project(file="/p/dev_console_project.py"):
    def alpha(ctx):
        """a"""
        return "a"

    def beta_two(ctx):
        return "b"

    beta_two.fake = True
    return SimpleNamespace(__file__=file, WIDGETS={"x.created": [alpha, beta_two]}, EXPECTED_WIDGETS={}, HOME="Alpha",
                           MODULE_WIDGETS={"Mod": ("x.created", "Alpha")})


class Widgets(Base):
    def test_table_mirrors_projects_and_follows_a_reload(self):
        HM.init()
        mod = fake_project()
        self.assertTrue(ST.sync_widgets({"demo": mod}))
        db = sqlite3.connect(self.db)
        db.row_factory = sqlite3.Row
        rows = {r["id"]: r for r in db.execute("SELECT * FROM widgets")}
        self.assertEqual(sorted(rows), ["demo/x.created/Alpha", "demo/x.created/BetaTwo"])
        a = rows["demo/x.created/Alpha"]
        self.assertEqual((a["domain"], a["event"], a["name"], a["kind"], a["function"], a["fake"]), ("demo", "x.created", "Alpha", "widget", "alpha", 0))
        self.assertEqual(json.loads(a["roles"]), ["module:Mod", "home"])
        self.assertIn("def alpha(ctx)", a["code"])
        self.assertEqual(len(a["code_sha256"]), 64)
        self.assertEqual(rows["demo/x.created/BetaTwo"]["fake"], 1)
        self.assertFalse(ST.sync_widgets({"demo": mod}))  # nothing changed: nothing written
        # a hot reload with one widget fewer and one more domain
        mod.WIDGETS = {"x.created": [mod.WIDGETS["x.created"][0]]}
        self.assertTrue(ST.sync_widgets({"demo": mod, "other": fake_project("/q/dev_console_project.py")}))
        ids = [r[0] for r in db.execute("SELECT id FROM widgets ORDER BY id")]
        self.assertEqual(ids, ["demo/x.created/Alpha", "other/x.created/Alpha", "other/x.created/BetaTwo"])

    def test_the_logo_is_a_real_widget_of_the_console_project(self):
        sys.path.insert(0, str(HERE))
        import importlib.util
        spec = importlib.util.spec_from_file_location("dev_console_project_t", HERE / "dev_console_project.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ST.sync_widgets({"dev-console": mod})
        row = sqlite3.connect(self.db).execute("SELECT name, event, fake FROM widgets WHERE id=?", (ST.LOGO_ID,)).fetchone()
        self.assertEqual(row, ("Logo", "domain.updated", 1))


class Stream(Base):
    def test_a_write_from_another_process_reaches_the_stream(self):
        HM.init()

        async def run():
            gen = ST.changes(rust_timeout=1000)
            first = json.loads(await asyncio.wait_for(gen.__anext__(), 10))
            self.assertEqual([w["id"] for w in first["widgets"]], ["logo"])
            script = ("import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); d.execute(\"INSERT INTO home (id,source,content,title,position,span,created_at,updated_at)"
                      " VALUES ('ext','html','<i>x</i>','Ext',5,1,'t','t')\"); d.commit()")
            await asyncio.create_subprocess_exec(sys.executable, "-c", script, str(self.db))
            ids = []
            while "ext" not in ids:  # the next snapshot that differs
                ids = [w["id"] for w in json.loads(await asyncio.wait_for(gen.__anext__(), 10))["widgets"]]
            await gen.aclose()
            return ids

        self.assertEqual(asyncio.run(run()), ["logo", "ext"])


class LiveConsole(unittest.TestCase):
    """A real console on a test port: routes, SSE headers, the external edit, the widgets table."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "reg").mkdir()  # the registry's folder is watched by the reloader: the database lives beside it, never inside
        (tmp / "reg" / "registry").write_text("")
        cls.db = tmp / "db" / "dev-console.sqlite"
        env = {**os.environ, "DEV_CONSOLE_REGISTRY": str(tmp / "reg" / "registry"), "COSTS_DIR": str(tmp / "costs"),
               "DEV_CONSOLE_DB": str(cls.db), "DEV_CONSOLE_HOME_DIR": str(tmp / "home")}
        cls.proc = subprocess.Popen(
            ["uv", "run", "--script", str(HERE / "dev-console.py"), "--project", str(HERE / "dev_console_project.py"), "--port", str(PORT)],
            cwd=str(tmp), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while True:
            if cls.proc.poll() is not None:
                raise RuntimeError("console exited before answering")
            try:
                cls.get("/api/home")
                break
            except OSError:
                pass

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=20)
        cls.tmp.cleanup()

    @classmethod
    def get(cls, path):
        return urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=15).read().decode()

    @classmethod
    def post(cls, path, body):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", json.dumps(body).encode(), {"X-Devc-Actor": "tester"})
        return json.loads(urllib.request.urlopen(req, timeout=15).read())

    def test_routes_stream_external_edit_and_catalogue(self):
        ids = lambda: [w["id"] for w in json.loads(self.get("/api/home"))["widgets"]]
        self.assertEqual(ids(), ["logo"])
        self.assertIn("<svg", self.get("/domain/dev-console/w/_/domain.updated/Logo"))
        self.post("/api/home/show", {"id": "a", "source": "html", "content": "<p>a</p>"})
        self.post("/api/home/show", {"id": "b", "source": "html", "content": "<p>b</p>"})
        self.assertEqual(ids(), ["logo", "a", "b"])
        resp = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/home/stream", timeout=15)
        self.assertIn("text/event-stream", resp.headers["content-type"])
        snap = lambda: json.loads(resp.readline().decode()[6:])["widgets"]
        self.assertEqual([w["id"] for w in snap()], ["logo", "a", "b"])
        resp.readline()  # the blank line that ends the event
        db = sqlite3.connect(self.db)  # the owner, in a SQLite app: move b to the top
        db.execute("UPDATE home SET position=-1 WHERE id='b'")
        db.commit()
        self.assertEqual([w["id"] for w in snap()], ["b", "logo", "a"])
        resp.close()
        self.post("/api/home/clear", {})
        self.assertEqual(ids(), ["logo"])
        n = sqlite3.connect(self.db).execute("SELECT count(*) FROM widgets WHERE domain='dev-console'").fetchone()[0]
        self.assertGreaterEqual(n, 9)


if __name__ == "__main__":
    unittest.main()
