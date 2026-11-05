# /// script
# requires-python = ">=3.11"
# ///
"""The flow end to end, on temporary journals: feedback and styles, the model registry, and the parallel execute.

Run: uv run --script scripts/test_flow.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["TASKS_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).parent))
import tasks  # noqa: E402

# a fake pi, first on PATH when a test asks for it: answers as pi's --mode json would (the models listing, one
# assistant turn with usage) without any model call, and logs what it was asked
FAKE_PI = r'''#!/bin/sh
# fake pi: listing, or one assistant turn as JSONL, no model.
log="${FAKE_PI_LOG:-/dev/null}"
model=
prev=
prompt=
for a in "$@"; do
  case "$a" in
    --list-models|--list-models=*)
      printf 'provider       model              context  max-out  thinking  images\n'
      printf 'claude-bridge  claude-sonnet-5-5  1M       128K     yes       yes\n'
      printf 'zai            glm-5.3            1M       131.1K   yes       no\n'
      printf 'zai            glm-5.3-flash      1M       131.1K   yes       yes\n'
      exit 0
      ;;
  esac
  if [ "$prev" = "--model" ]; then model="$a"; fi
  prompt="$a"
  prev="$a"
done
where="$(pwd)"
name="${model#*/}"
printf '%s\n' '{"type":"session","version":3,"id":"fake-session","timestamp":0,"cwd":"."}'
printf '%s\n' '{"type":"agent_start"}'
printf '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"feito por %s em %s"}],"usage":{"input":10,"output":5,"cacheRead":0,"cacheWrite":0,"totalTokens":15,"cost":{"input":0,"output":0,"cacheRead":0,"cacheWrite":0,"total":0}},"provider":"%s","model":"%s","responseModel":"%s","stopReason":"stop"}}\n' "$model" "$where" "${model%%/*}" "$name" "$name"
printf '%s\n' '{"type":"turn_end","message":{"role":"assistant"},"toolResults":[]}'
printf '%s\n' '{"type":"agent_end","messages":[],"willRetry":false}'
printf '%s\n' '{"type":"agent_settled","aborted":false}'
printf '%s %s %s\n' "$model" "$where" "${#prompt}" >>"$log"
exit "${FAKE_PI_EXIT:-0}"
'''
FAKE_BIN = Path(tempfile.mkdtemp())
(FAKE_BIN / "pi").write_text(FAKE_PI, encoding="utf-8")
(FAKE_BIN / "pi").chmod(0o755)


def fake_env(**extra) -> dict[str, str]:
    """os.environ overrides with the fake pi first on PATH."""
    return {"PATH": f"{FAKE_BIN}{os.pathsep}{os.environ.get('PATH', '')}", **extra}


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


class Models(unittest.TestCase):
    def test_registry(self):
        ids = tasks.models_registry()
        self.assertTrue({"sonnet", "glm", "glm-flash"} <= set(ids))
        self.assertEqual(tasks.default_model(), "sonnet")
        sonnet = tasks.resolve_model("sonnet")
        self.assertEqual((sonnet["model"], sonnet["provider"], sonnet["plan"]),
                         ("claude-bridge/claude-sonnet-5-5", "claude-bridge", "mukutu-claude"))
        self.assertEqual(tasks.resolve_model("glm")["model"], "zai/glm-5.3")
        self.assertEqual(tasks.resolve_model("glm-flash")["model"], "zai/glm-5.3-flash")
        # the GLM key is a file recipe (@~/glm_token), never a value in the registry
        self.assertEqual(ids["glm"]["env"]["ZAI_API_KEY"], "@~/glm_token")
        self.assertEqual(ids["sonnet"]["env"]["CLAUDE_CONFIG_DIR"], "~/.claude-mukutu")
        with self.assertRaisesRegex(ValueError, "modelo desconhecido"):
            tasks.resolve_model("nope")

    def test_config_env_recipe_and_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            key = Path(d) / "key"
            key.write_text(" sekret \n", encoding="utf-8")
            cfg = Path(d) / "config.json"
            cfg.write_text(json.dumps({"models": {
                "glm": {"env": {"ZAI_API_KEY": f"@{key}"}},
                "turbo": {"model": "openrouter/z-ai/glm-5.3", "name": "GLM por token"},
                "anthropic": {"model": "~anthropic/claude-sonnet-5"}},
                "default_model": "glm"}), encoding="utf-8")
            with patch.dict(os.environ, {"TASKS_CONFIG": str(cfg)}):
                self.assertEqual(tasks.default_model(), "glm")
                env = tasks._model_env(tasks.resolve_model("glm"))
                self.assertEqual(env["ZAI_API_KEY"], "sekret")  # the file's content, to the child process only
                self.assertNotEqual(os.environ.get("ZAI_API_KEY"), "sekret")  # never this process's env
                for bad in ("turbo", "anthropic"):  # OpenRouter and any per-token provider: refused
                    with self.assertRaisesRegex(ValueError, "recusado"):
                        tasks.resolve_model(bad)

    def test_overview_lists_and_usability(self):
        with tempfile.TemporaryDirectory() as d:
            key = Path(d) / "key"
            key.write_text("k", encoding="utf-8")
            cfg = Path(d) / "config.json"
            cfg.write_text(json.dumps({"models": {"glm": {"env": {"ZAI_API_KEY": f"@{key}"}},
                                                  "glm-flash": {"env": {"ZAI_API_KEY": f"@{key}"}}}}),
                           encoding="utf-8")
            with patch.dict(os.environ, fake_env(TASKS_CONFIG=str(cfg))):
                out = tasks.models_overview()
                self.assertEqual(out["default"], "sonnet")
                self.assertEqual([out["models"][m]["usable"] for m in ("sonnet", "glm", "glm-flash")],
                                 [True, True, True])
                self.assertEqual(out["models"]["sonnet"]["plan"], "mukutu-claude")
                self.assertEqual(out["models"]["glm"]["plan"], "glm-coding-plan")


class ExecuteParallel(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.repo = self.home / "repo"
        self.repo.mkdir()
        for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "test@example.com"],
                    ["git", "config", "user.name", "test"]):
            subprocess.run(cmd, cwd=self.repo, check=True, capture_output=True)
        (self.repo / "README.md").write_text("# repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=self.repo, check=True, capture_output=True)
        key = self.home / "key"
        key.write_text("test-key", encoding="utf-8")
        cfg = self.home / "config.json"
        cfg.write_text(json.dumps({"models": {"glm": {"env": {"ZAI_API_KEY": f"@{key}"}},
                                              "glm-flash": {"env": {"ZAI_API_KEY": f"@{key}"}}}}),
                       encoding="utf-8")
        self.log = self.home / "pi.log"
        self.env = fake_env(TASKS_CONFIG=str(cfg), TASKS_DIR=str(self.home / "journal"),
                            FAKE_PI_LOG=str(self.log))

    def _task(self, journal) -> str:
        tid = journal.emit("task.explained", {"title": "Relatório mensal de vendas", "text": "Monta o relatório"},
                           actor="gabriel")["task_id"]
        journal.emit("understanding.taught_back", {"text": "vou montar a planilha"}, tid)
        journal.emit("understanding.confirmed", {"text": "bate"}, tid)
        return tid

    def test_parallel_models(self):
        with patch.dict(os.environ, self.env):
            j = tasks.TasksJournal()
            tid = self._task(j)
            records = tasks.execute(tid, cwd=str(self.repo), models=["sonnet", "glm"])
            self.assertEqual([r["value"]["model"] for r in records], ["sonnet", "glm"])  # one per model, in order
            first, second = records
            for r in records:
                v = r["value"]
                self.assertEqual((v["harness"], v["method"]), ("pi", "print"))
                self.assertEqual(v["exit_code"], 0)
                self.assertGreaterEqual(v["duration_s"], 0)
                self.assertGreaterEqual(v["cycle_time_s"], 0)
                self.assertEqual((v["turns"], v["tokens"], v["cost_usd"]), (1, 15, 0))
                self.assertTrue(Path(v["worktree"]).is_dir())
                branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=v["worktree"],
                                        capture_output=True, text=True).stdout.strip()
                self.assertEqual(branch, v["branch"])  # each run worked on its own branch
            self.assertEqual((first["value"]["provider"], first["value"]["plan"]), ("claude-bridge", "mukutu-claude"))
            self.assertEqual((second["value"]["provider"], second["value"]["plan"]), ("zai", "glm-coding-plan"))
            self.assertEqual(first["value"]["worktree"], str(self.home / f"repo.task-{tid[:8]}-sonnet"))
            self.assertEqual(first["value"]["branch"], f"task/{tid[:8]}-sonnet")
            self.assertNotEqual(first["value"]["worktree"], second["value"]["worktree"])
            self.assertIn(f"feito por claude-bridge/claude-sonnet-5-5 em {first['value']['worktree']}",
                          first["value"]["text"])
            # the projector: executed, the result is the last model's answer
            state = j.read({"id": tid})
            self.assertEqual(state["status"], "executed")
            self.assertIn("feito por zai/glm-5.3", state["result"])
            # both runs really happened, each from its own worktree, each with the whole prompt
            calls = [line.split() for line in self.log.read_text().splitlines()]
            self.assertEqual({c[0] for c in calls}, {"claude-bridge/claude-sonnet-5-5", "zai/glm-5.3"})
            self.assertEqual({c[1] for c in calls}, {first["value"]["worktree"], second["value"]["worktree"]})
            self.assertTrue(all(int(c[2]) > 50 for c in calls))
            # ExecutionResult of a pi run (the new fields, and the old ones it does not invent)
            x = tasks.result_from(second["value"])
            self.assertEqual((x.provider, x.plan, x.model, x.harness), ("zai", "glm-coding-plan", "glm", tasks.Harness.PI))
            self.assertEqual(x.branch, f"task/{tid[:8]}-glm")
            self.assertIsNone(x.effort)

    def test_result_from_keeps_older_events(self):
        old_full = {"text": "x", "method": "print", "harness": "claude-code", "model": "sonnet", "effort": "medium",
                    "cycle_time_s": 10, "delivery": "pr_open", "session": {"id": "s", "log": "l", "harness": "claude-code"},
                    "pull_request": {"number": 7, "url": "http://pr", "state": "merged"}}
        x = tasks.result_from(old_full)
        self.assertEqual((x.model, x.session.id, x.pull_request.number), (tasks.Model.SONNET, "s", 7))
        self.assertEqual((x.provider, x.worktree, x.turns), ("", "", None))
        self.assertIsNone(tasks.result_from({"text": "x", "exit_code": 1, "executor": "claude"}))  # 0.4-0.5 run
        self.assertIsNone(tasks.result_from({"text": "x"}))

    def test_unknown_and_refused_never_run(self):
        with patch.dict(os.environ, self.env):
            j = tasks.TasksJournal()
            tid = self._task(j)
            with self.assertRaisesRegex(ValueError, "modelo desconhecido"):
                tasks.execute(tid, cwd=str(self.repo), models=["nope"])
            cfg = json.loads(Path(os.environ["TASKS_CONFIG"]).read_text(encoding="utf-8"))
            cfg["models"]["turbo"] = {"model": "openrouter/z-ai/glm-5.3"}
            Path(os.environ["TASKS_CONFIG"]).write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "recusado"):
                tasks.execute(tid, cwd=str(self.repo), models=["turbo"])
            self.assertFalse(self.log.exists())  # nothing ran
            self.assertEqual([e for e in j.read({"history": True}) if e["event"] == "task.executed"], [])
            self.assertEqual({p.name for p in self.home.iterdir()}, {"repo", "key", "config.json", "journal"})  # no worktree

    def test_default_model_runs_when_none_is_given(self):
        with patch.dict(os.environ, self.env):
            j = tasks.TasksJournal()
            tid = self._task(j)
            records = tasks.execute(tid, cwd=str(self.repo))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["value"]["model"], "sonnet")


if __name__ == "__main__":
    unittest.main()
