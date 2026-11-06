# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of console_reload.py: a changed helper is read again, and the watcher knows the folders a project imports.
Run: uv run --script test_console_reload.py   (temp folders, invented modules)"""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import console_reload as cr  # noqa: E402


class Reload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()
        (self.dir / "helper_x.py").write_text("def value():\n    return 1\n")
        sys.path.insert(0, str(self.dir))

    def tearDown(self):
        sys.path.remove(str(self.dir))
        sys.modules.pop("helper_x", None)
        self.tmp.cleanup()

    def test_changed_helper_is_read_again_after_purge(self):
        import helper_x
        self.assertEqual(helper_x.value(), 1)
        (self.dir / "helper_x.py").write_text("def value():\n    return 22\n")
        importlib.invalidate_caches()
        self.assertEqual(importlib.import_module("helper_x").value(), 1)  # cached: the bug
        self.assertEqual(cr.purge([self.dir]), ["helper_x"])
        self.assertEqual(importlib.import_module("helper_x").value(), 22)

    def test_purge_keeps_names_and_other_folders(self):
        import helper_x  # noqa: F401
        self.assertEqual(cr.purge([self.dir], keep=("helper_x",)), [])
        self.assertEqual(cr.purge([self.dir / "elsewhere"]), [])
        self.assertIn("os", sys.modules)  # the stdlib is never purged

    def test_purge_never_drops_the_console_itself(self):
        main = type(sys)("__main__x")
        main.__file__ = str(self.dir / "dev-console.py")
        sys.modules["__main__x"] = main
        try:
            self.assertEqual(cr.purge([self.dir]), [])
        finally:
            sys.modules.pop("__main__x")

    def test_watch_dirs_has_project_extra_and_loaded_module_folders(self):
        import helper_x
        extra = self.dir / "extra"
        extra.mkdir()
        proj = self.dir / "proj" / "dev_console_project.py"
        proj.parent.mkdir()
        proj.write_text("")
        got = cr.watch_dirs([proj], modules={"helper_x": helper_x}, extra_paths=[extra, "/nonexistent"])
        self.assertEqual(got, {proj.parent, extra, self.dir})

    def test_library_folders_are_not_watched(self):
        self.assertEqual(cr.watch_dirs([], modules={"json": importlib.import_module("json")}), set())


if __name__ == "__main__":
    unittest.main()
