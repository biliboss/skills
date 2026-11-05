"""The feedback and style flow end to end, on a temporary journal.  Run: uv run python scripts/test_flow.py"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["TASKS_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).parent))
import tasks  # noqa: E402


class Flow(unittest.TestCase):
    def test_flow(self):
        j = tasks.TasksJournal()
        tid = j.emit("task.explained", {"title": "Relatório mensal de vendas", "text": "Monta o relatório mensal de vendas"},
                     actor="gabriel")["task_id"]
        j.emit("understanding.taught_back", {"text": "vou montar a planilha", "style": "direto"}, tid)
        j.emit("learning.recorded", {"text": "sempre planilha mensal de vendas, nunca PDF"}, tid)

        used = tasks.use_learnings(tid)
        self.assertEqual(len(used["value"]["learning_ids"]), 1)
        self.assertIsNone(tasks.use_learnings(tid))  # already used on this task

        # another task shares two words with the learning: it applies there too
        other = j.emit("task.explained", {"title": "Vendas do mês", "text": "relatório mensal"}, actor="gabriel")["task_id"]
        self.assertIsNotNone(tasks.use_learnings(other))

        out = tasks.feedback(tid, "ficou seco")
        self.assertEqual(len(out["styles"]), 3)
        self.assertEqual(tasks.style_scores()["direto"], -1)
        self.assertNotEqual(tasks.default_style(), "direto")

        tasks.generate_options(tid, {"direto": "a", "passo-a-passo": "b", "exemplo": "c"})
        options = j.read({"id": tid})["options"]
        self.assertEqual(len(options), 3)
        pick = next(o for o in options if o["style"] == "exemplo")
        tasks.choose(tid, pick["id"])
        state = j.read({"id": tid})
        self.assertEqual((state["style"], state["options"], state["status"]), ("exemplo", [], "taught_back"))
        self.assertEqual(tasks.style_scores()["exemplo"], 1)
        self.assertEqual(tasks.default_style(), "exemplo")

        j.emit("understanding.confirmed", {"text": "bate"}, tid)
        self.assertEqual(j.read({"id": tid})["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
