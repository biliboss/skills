# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of shape.py: emit validation, projection, listing. Run: uv run --script test_shape.py
(stdlib unittest, a temp SHAPE_DIR; the real journal is never touched)"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import shape  # noqa: E402


class ShapeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SHAPE_DIR"] = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def emit(self, event, value, sid="s1"):
        return shape.emit(event, value, sid, "test")

    def test_emit_writes_a_row(self):
        row = self.emit("request.received", {"text": "faz um site"})
        self.assertEqual(len(row["id"]), 12)
        self.assertRegex(row["at"], r"[+-]\d\d:\d\d$")
        self.assertEqual(len(shape._all_events()), 1)

    def test_unknown_event_and_bad_values_are_refused(self):
        with self.assertRaises(ValueError):
            self.emit("request.nope", {"text": "x"})
        with self.assertRaises(ValueError):
            self.emit("piece.routed", {"piece": "magic"})
        with self.assertRaises(ValueError):
            self.emit("work.delegated", {"to": "nobody"})
        with self.assertRaises(ValueError):
            self.emit("request.received", {})
        with self.assertRaises(ValueError):
            shape.emit("request.received", {"text": "x"}, "")

    def test_projection_follows_the_story(self):
        self.emit("request.received", {"text": "faz um site"})
        self.emit("piece.routed", {"piece": "pelo-resultado"})
        self.emit("understanding.taught_back", {"text": "um site para X"})
        s = shape.shapings()[0]
        self.assertEqual((s["request"], s["piece"], s["status"]), ("faz um site", "pelo-resultado", "taught_back"))
        self.emit("understanding.confirmed", {"text": "ok"})
        self.emit("work.delegated", {"to": "subagent"})
        s = shape.ShapeJournal().read({"id": "s1"})
        self.assertEqual((s["status"], s["delegated_to"]), ("delegated", "subagent"))

    def test_list_filters_by_status_and_keeps_shapings_apart(self):
        self.emit("request.received", {"text": "a"}, "a")
        self.emit("request.received", {"text": "b"}, "b")
        self.emit("piece.routed", {"piece": "direct"}, "b")
        self.assertEqual(len(shape.shapings()), 2)
        self.assertEqual([s["id"] for s in shape.shapings("routed")], ["b"])

    def test_transitions_only_name_real_events(self):
        valid = {f"{d}.{k}" for d, kinds in shape.EVENTS.items() for k in kinds.values()}
        for src, dsts in shape.TRANSITIONS.items():
            self.assertIn(src, valid)
            self.assertTrue(set(dsts) <= valid)

    def test_cli_main(self):
        self.assertEqual(shape.main(["emit", "request.received", '{"text":"x"}', "--shaping", "z", "--actor", "t"]), 0)
        self.assertEqual(shape.main(["emit", "piece.routed", '{"piece":"x"}', "--shaping", "z", "--actor", "t"]), 2)
        self.assertEqual(shape.main(["list"]), 0)


class LoopTest(ShapeTest):
    def walk(self, sid="L"):
        self.emit("request.received", {"text": "faz"}, sid)
        self.emit("piece.routed", {"piece": "direct"}, sid)
        self.emit("understanding.taught_back", {"text": "v1"}, sid)
        self.emit("backbrief.attempted", {"n": 1}, sid)

    def test_third_attempt_is_refused_and_the_line_opens_instead(self):
        self.walk()
        self.emit("understanding.taught_back", {"text": "v2"}, "L")
        with self.assertRaises(ValueError):  # the line needs 2 attempts first
            self.emit("understanding.line_opened", {"tool": "clarify"}, "L")
        self.emit("backbrief.attempted", {"n": 2}, "L")
        with self.assertRaises(ValueError) as cm:
            self.emit("backbrief.attempted", {"n": 3}, "L")
        self.assertIn("open the line", str(cm.exception))
        with self.assertRaises(ValueError):
            self.emit("understanding.line_opened", {"tool": "chat"}, "L")
        self.emit("understanding.line_opened", {"tool": "interview"}, "L")
        s = shape.shapings()[0]
        self.assertEqual((s["attempts"], s["line"], s["status"]), (2, "interview", "line_opened"))

    def test_attempts_show_in_the_projection(self):
        self.walk()
        self.assertEqual(shape.shapings()[0]["attempts"], 1)

    def test_widget_text(self):
        sys.modules.setdefault("fasthtml", type(sys)("fasthtml"))
        sys.modules["fasthtml.common"] = type(sys)("fasthtml.common")
        for n in ("Div", "P", "Span"):
            setattr(sys.modules["fasthtml.common"], n, lambda *a, **k: None)
        import dev_console_project as w
        self.assertEqual(w.attempts_text({"attempts": 2}), "2/3")
        self.assertEqual(w.attempts_text({"attempts": 2, "line": "clarify"}), "⇡ clarify")
        self.assertEqual(w.cost_text({"est_cost_brl": 12, "real_cost_brl": 15.5}), "est R$ 12,00 · real R$ 15,50")


class CatalogTest(ShapeTest):
    def setUp(self):
        super().setUp()
        self.cat = Path(self.tmp.name) / "resources.json"
        self.cat.write_text((Path(__file__).parent.parent / "references" / "resources.json").read_text())
        os.environ["SHAPE_CATALOG"] = str(self.cat)
        os.environ["SHAPE_LEARN_PR"] = "0"
        self.addCleanup(lambda: [os.environ.pop(k) for k in ("SHAPE_CATALOG", "SHAPE_LEARN_PR")])

    def test_catalog_covers_the_house(self):
        cat = shape.load_catalog()["resources"]
        skills = Path(__file__).resolve().parents[2]
        for d in skills.iterdir():
            if (d / "SKILL.md").exists():
                self.assertIn(f"skill:{d.name}", cat)
        for k in ("profile:hacker", "profile:mantainer", "model:haiku", "model:opus", "form:subagent", "form:here"):
            self.assertIn(k, cat)
        for r in cat.values():
            self.assertTrue({"what_for", "est_minutes", "est_tokens", "est_cost_brl", "source"} <= set(r))

    def test_choose_picks_the_least_cost(self):
        pick = shape.choose("small-edit")
        self.assertIn("model:haiku", pick["resources"])
        self.assertIn("form:here", pick["resources"])
        self.assertTrue(pick["why"].startswith("é o menor custo"))
        self.assertEqual(shape.main(["choose", "code-change", "--shaping", "c"]), 0)
        self.assertEqual(shape.shapings()[0]["est_cost_brl"], shape.choose("code-change")["est_cost_brl"])
        with self.assertRaises(ValueError):
            shape.choose("nope")

    def test_resources_chosen_and_closed_validate(self):
        with self.assertRaises(ValueError):
            self.emit("resources.chosen", {"resources": [], "est_minutes": 1, "est_cost_brl": 1, "why": "x"})
        with self.assertRaises(ValueError):
            self.emit("resources.chosen", {"resources": ["a"], "est_minutes": 1, "est_cost_brl": 1})
        with self.assertRaises(ValueError):
            self.emit("shaping.closed", {"real_minutes": "x", "real_cost_brl": 1})

    def close(self, sid, est_min, est_brl, real_min, real_brl, res=("form:subagent",)):
        self.emit("resources.chosen", {"resources": list(res), "est_minutes": est_min, "est_cost_brl": est_brl,
                                       "why": "Decidi x porque y"}, sid)
        self.emit("shaping.closed", {"real_minutes": real_min, "real_cost_brl": real_brl}, sid)

    def test_learn_moves_the_estimate_and_the_source(self):
        before = shape.load_catalog()["resources"]["form:subagent"]
        self.close("a", 10, 4, 20, 8)  # took twice what was estimated
        self.assertEqual(shape.main(["learn", "--no-pr"]), 0)
        after = shape.load_catalog()
        r = after["resources"]["form:subagent"]
        self.assertGreater(r["est_minutes"], before["est_minutes"])
        self.assertGreater(r["est_cost_brl"], before["est_cost_brl"])
        self.assertTrue(r["source"].endswith(" + shape n=1"), r["source"])
        self.assertTrue(r["source"].startswith("journal:~/.hermes/"))
        self.assertEqual(after["resources"]["skill:shape"]["source"], "estimate")
        self.assertEqual(after["learn"]["closed_seen"], 1)
        # a second learn with nothing new changes nothing
        _, diff = shape.learn()
        self.assertEqual(diff, [])

    def test_autolearn_after_ten_closed(self):
        for i in range(10):
            self.close(f"s{i}", 5, 1, 5, 1)
        self.emit("request.received", {"text": "x"}, "z")
        shape.maybe_autolearn()
        self.assertEqual(shape.load_catalog()["learn"]["closed_seen"], 10)


if __name__ == "__main__":
    unittest.main()
