# /// script
# requires-python = ">=3.11"
# ///
"""The flow end to end, on temporary journals: feedback and styles, the model registry, the parallel execute, and
verify (IV&V) → deliver → the PR decision.

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
if [ -n "$FAKE_PI_ARGS" ]; then  # every argument of the call, RS-separated, one call per GS
  for a in "$@"; do printf '%s\036' "$a" >>"$FAKE_PI_ARGS"; done
  printf '\035' >>"$FAKE_PI_ARGS"
fi
printf '%s\n' '{"type":"session","version":3,"id":"fake-session","timestamp":0,"cwd":"."}'
printf '%s\n' '{"type":"agent_start"}'
if [ -n "$FAKE_PI_ANSWER_FILE" ] && [ -f "$FAKE_PI_ANSWER_FILE" ]; then  # a canned assistant message_end line
  cat "$FAKE_PI_ANSWER_FILE"
else
printf '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"feito por %s em %s"}],"usage":{"input":10,"output":5,"cacheRead":0,"cacheWrite":0,"totalTokens":15,"cost":{"input":0,"output":0,"cacheRead":0,"cacheWrite":0,"total":0}},"provider":"%s","model":"%s","responseModel":"%s","stopReason":"stop"}}\n' "$model" "$where" "${model%%/*}" "$name" "$name"
fi
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
    def test_intent_of_the_outcome_mode(self):
        j = tasks.TasksJournal()
        tid = j.emit("task.explained", {"title": "Site", "text": "faz site pro Via"}, actor="gabriel")["task_id"]
        intent = {"why": "corretores pela busca", "who": "corretor", "result": "cadastros ref=blog em 90 dias",
                  "limits": "nada publicado sem ok", "done_when": "4 semanas subindo", "bet": "CTR de como-tirar-creci"}
        for bad in ({"nope": "x"}, "texto", {"why": 3}):
            with self.assertRaises(ValueError):
                j.emit("understanding.taught_back", {"text": "t", "intent": bad}, tid)
        e = j.emit("understanding.taught_back", {"text": "t", "intent": intent}, tid)
        self.assertEqual(e["value"]["intent"], intent)
        j.emit("understanding.taught_back", {"text": "sem intent"}, tid)  # the field stays optional

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


class RepoCase(unittest.TestCase):
    """A scratch git repo, a config with the GLM key recipe, a journal of its own and the fake pi."""

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
        self.args = self.home / "pi.args"
        self.answer = self.home / "answer.jsonl"
        self.env = fake_env(TASKS_CONFIG=str(cfg), TASKS_DIR=str(self.home / "journal"),
                            FAKE_PI_LOG=str(self.log), FAKE_PI_ARGS=str(self.args),
                            FAKE_PI_ANSWER_FILE=str(self.answer))

    def say(self, text: str) -> None:
        """What the next pi run answers (one assistant message, as pi's JSON stream carries it)."""
        self.answer.write_text(json.dumps({"type": "message_end", "message": {
            "role": "assistant", "content": [{"type": "text", "text": text}], "model": "fake", "responseModel": "fake",
            "usage": {"totalTokens": 7, "cost": {"total": 0}}, "stopReason": "stop"}}) + "\n", encoding="utf-8")

    def verdict(self, passed: bool, checks: list[dict] | None = None, summary: str = "ok") -> None:
        """The verifier answers: prose, then the last JSON block."""
        checks = checks if checks is not None else [{"what": "testes", "how": "rodei", "evidence": "OK", "passed": passed}]
        self.say("Conferi o worktree.\n```json\n" + json.dumps({"passed": passed, "summary": summary, "checks": checks})
                 + "\n```")

    def calls(self) -> list[list[str]]:
        """Every pi call so far: its arguments, the prompt last."""
        raw = self.args.read_text(encoding="utf-8") if self.args.exists() else ""
        return [c.split("\x1e")[:-1] for c in raw.split("\x1d") if c]

    def _task(self, journal) -> str:
        tid = journal.emit("task.explained", {"title": "Relatório mensal de vendas", "text": "Monta o relatório"},
                           actor="gabriel")["task_id"]
        journal.emit("understanding.taught_back", {"text": "vou montar a planilha"}, tid)
        journal.emit("learning.recorded", {"text": "SEGREDO-DO-EXECUTOR: sempre em planilha"}, tid)
        journal.emit("understanding.confirmed", {"text": "bate"}, tid)
        return tid


class ExecuteParallel(RepoCase):

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

    def test_result_from_never_raises_on_what_the_real_journal_holds(self):
        pi = {"method": "pi", "harness": "pi", "model": "glm", "effort": "high", "cycle_time_s": 9, "delivery": "PR aberto",
              "pull_request": "https://github.com/o/r/pull/49", "exit_code": 0, "worktree": "w"}
        x = tasks.result_from(pi)  # method "pi", delivery in words, the PR as a bare URL
        self.assertEqual((x.method, x.pull_request.number, x.pull_request.state), (tasks.Method.PI, 49, tasks.PullRequestState.OPEN))
        y = tasks.result_from({**pi, "method": "claude-code", "delivery": "PR fechado"})  # a value no enum knows is kept, not a 500
        self.assertEqual((y.method, y.pull_request.state), ("claude-code", tasks.PullRequestState.CLOSED))
        self.assertEqual(tasks.result_from({**pi, "method": "by-hand"}).method, "by-hand")

    def test_result_from_reads_a_hermes_spawn(self):
        v = {"text": "done", "harness": "hermes", "method": "spawn", "profile": "researcher", "session_id": "s1",
             "exit_code": 0, "duration_s": 12.5, "worktree": "/repo"}
        x = tasks.result_from(v)
        self.assertEqual((x.method, x.harness, x.worktree), (tasks.Method.SPAWN, tasks.Harness.HERMES, "/repo"))

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


class Verify(RepoCase):
    """verify (IV&V), deliver and the PR decision."""

    def start(self):
        """A confirmed task executed once on sonnet: (journal, task id, the task.executed record)."""
        j = tasks.TasksJournal()
        tid = self._task(j)
        run = tasks.execute(tid, cwd=str(self.repo))[0]
        return j, tid, run

    def test_verify_passes(self):
        with patch.dict(os.environ, self.env):
            j, tid, run = self.start()
            self.verdict(True, [{"what": "testes", "how": "uv run test", "evidence": "12 OK", "passed": True},
                                {"what": "o app instalado", "how": "abri", "evidence": "abriu", "passed": True}], "tudo certo")
            rec = tasks.verify(tid, model="glm", actor="verificador")
            v = rec["value"]
            self.assertEqual((rec["event"], rec["actor"], v["passed"]), ("task.verified", "verificador", True))
            self.assertEqual((v["model"], v["provider"], v["plan"], v["exit_code"]), ("glm", "zai", "glm-coding-plan", 0))
            self.assertGreaterEqual(v["duration_s"], 0)
            self.assertEqual([c["what"] for c in v["checks"]], ["testes", "o app instalado"])
            self.assertIn("passou: 2 de 2", v["text"])
            self.assertIn("tudo certo", v["text"])
            self.assertEqual(v["executed_id"], run["id"])
            state = j.read({"id": tid})
            self.assertEqual((state["status"], state["verification"]["passed"]), ("verified", True))
            # the verifier ran on the registry model, in print mode, with no session, from the delivery's worktree
            *_, last = self.calls()
            flags = last[:-1]
            self.assertEqual(flags[flags.index("--model") + 1], "zai/glm-5.3")
            self.assertTrue({"-p", "--no-session", "--mode", "json"} <= set(flags))
            self.assertNotIn("--session", flags)
            self.assertEqual(self.log.read_text().splitlines()[-1].split()[1], run["value"]["worktree"])
            # and the result of the run carries the verification
            x, _ = tasks.outcome_of(j.read({"id": tid, "history": True}))
            self.assertTrue(x.verification.passed)
            self.assertEqual(x.verification.checks[1].evidence, "abriu")
            self.assertIsNone(x.delivered)

    def test_verifier_prompt_has_only_the_request_and_the_delivery(self):
        with patch.dict(os.environ, self.env):
            j, tid, run = self.start()
            self.verdict(True)
            tasks.verify(tid)
            executor, verifier = (c[-1] for c in self.calls())
            self.assertIn("SEGREDO-DO-EXECUTOR", executor)  # the executor was told the adjustment
            self.assertNotIn("SEGREDO-DO-EXECUTOR", verifier)  # the verifier never sees what the executor saw
            self.assertNotIn("Execute a tarefa", verifier)  # nor the executor's prompt
            v = run["value"]
            for must in ("Monta o relatório",  # the task's text
                         "vou montar a planilha",  # the last confirmed teach-back
                         v["worktree"], v["branch"],  # the delivery under test
                         v["text"],  # the executor's report
                         "verificador independente", "último", '"passed"'):
                self.assertIn(must, verifier)
            self.assertNotIn("Relatório mensal de vendas", verifier)  # not even the title: only the text
            self.assertNotIn(v["session_id"] or "no-session-id", verifier)  # no trace of the executor's session

    def test_verify_fails_and_execute_runs_again(self):
        with patch.dict(os.environ, self.env):
            j, tid, _ = self.start()
            self.verdict(False, [{"what": "a planilha abre", "how": "abri", "evidence": "arquivo corrompido", "passed": False},
                                 {"what": "testes", "how": "rodei", "evidence": "OK", "passed": True}])
            rec = tasks.verify(tid)
            self.assertFalse(rec["value"]["passed"])
            self.assertIn("não passou: 1 de 2", rec["value"]["text"])
            state = j.read({"id": tid})
            self.assertEqual(state["status"], "confirmed")  # where execute is allowed again
            self.assertFalse(state["verification"]["passed"])
            with self.assertRaisesRegex(ValueError, "only an executed task is verified"):
                tasks.verify(tid)  # nothing new to verify until it runs again
            with self.assertRaisesRegex(ValueError, "passing verification"):
                tasks.deliver(tid, "direct")
            self.answer.unlink()
            tasks.execute(tid, cwd=str(self.repo))
            again = self.calls()[-1][-1]
            self.assertIn("não passou na verificação independente", again)  # the second run is told what failed
            self.assertIn("a planilha abre: arquivo corrompido", again)
            self.assertNotIn("testes: OK", again)  # only the checks that failed
            state = j.read({"id": tid})
            self.assertEqual((state["status"], state["verification"]), ("executed", None))
            self.verdict(True)
            self.assertTrue(tasks.verify(tid)["value"]["passed"])
            self.assertEqual(j.read({"id": tid})["status"], "verified")

    def test_unparsable_inconsistent_and_crashed_verifiers_do_not_pass(self):
        with patch.dict(os.environ, self.env):
            j, tid, _ = self.start()
            self.say("Parece tudo certo, passou.")  # no JSON block
            v = tasks.verify(tid)["value"]
            self.assertFalse(v["passed"])
            self.assertEqual(len(v["checks"]), 1)
            self.assertIn("sem bloco JSON", v["checks"][0]["evidence"])
            self.assertEqual(j.read({"id": tid})["status"], "confirmed")
            tasks.execute(tid, cwd=str(self.repo))
            # says passed, but one of its own checks did not
            self.verdict(True, [{"what": "a", "passed": True}, {"what": "b", "passed": False}])
            self.assertFalse(tasks.verify(tid)["value"]["passed"])
            tasks.execute(tid, cwd=str(self.repo))
            # a verifier that crashed never passes, whatever it printed
            self.verdict(True)
            with patch.dict(os.environ, {"FAKE_PI_EXIT": "3"}):
                v = tasks.verify(tid)["value"]
            self.assertEqual((v["passed"], v["exit_code"]), (False, 3))
            self.assertEqual(v["checks"][-1]["what"], "a execução do verificador")

    def test_verify_refuses_unknown_models_and_other_events(self):
        with patch.dict(os.environ, self.env):
            j = tasks.TasksJournal()
            tid = self._task(j)
            with self.assertRaisesRegex(ValueError, "only an executed task is verified"):  # still just confirmed
                tasks.verify(tid)
            tasks.execute(tid, cwd=str(self.repo))
            self.assertFalse(self.calls()[1:])
            cfg = json.loads(Path(os.environ["TASKS_CONFIG"]).read_text(encoding="utf-8"))
            cfg["models"]["turbo"] = {"model": "openrouter/z-ai/glm-5.3"}
            Path(os.environ["TASKS_CONFIG"]).write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "recusado"):  # per-token: never verifies either
                tasks.verify(tid, model="turbo")
            with self.assertRaisesRegex(ValueError, "modelo desconhecido"):
                tasks.verify(tid, model="nope")
            with self.assertRaisesRegex(ValueError, "no task.executed"):
                tasks.verify(tid, executed_id="nope")
            self.assertEqual(len(self.calls()), 1)  # only the executor ever ran
            with self.assertRaisesRegex(ValueError, "task.verified needs passed"):
                j.emit("task.verified", {"text": "x"}, tid)
            with self.assertRaisesRegex(ValueError, "task.delivered needs a kind"):
                j.emit("task.delivered", {"text": "x", "kind": "email"}, tid)

    def test_deliver_and_pr_decision_refusals(self):
        with patch.dict(os.environ, self.env):
            j, tid, _ = self.start()
            for call in (lambda: tasks.deliver(tid, "pr"), lambda: tasks.merge(tid),
                         lambda: tasks.request_review(tid, "olha")):
                with self.assertRaises(ValueError):  # executed, not verified: nothing after it is allowed
                    call()
            self.verdict(True)
            tasks.verify(tid)
            with self.assertRaisesRegex(ValueError, "task.delivered with kind pr"):
                tasks.merge(tid)  # verified, not delivered
            with self.assertRaisesRegex(ValueError, "kind is one of"):
                tasks.deliver(tid, "email")
            d = tasks.deliver(tid, "direct", text="issue criada no Linear", url="https://linear.app/x/1")
            self.assertEqual((d["event"], d["value"]["kind"], d["value"]["url"]), ("task.delivered", "direct", "https://linear.app/x/1"))
            self.assertEqual(j.read({"id": tid})["status"], "delivered")
            with self.assertRaisesRegex(ValueError, "task.delivered with kind pr"):
                tasks.merge(tid)  # a direct delivery has no PR to merge
            with self.assertRaisesRegex(ValueError, "task.delivered with kind pr"):
                tasks.request_review(tid, "olha")
            with self.assertRaisesRegex(ValueError, "passing verification"):
                tasks.deliver(tid, "none")  # delivered once is enough
            self.assertEqual([e["event"] for e in j.read({"id": tid, "history": True})][-3:],
                             ["task.executed", "task.verified", "task.delivered"])

    def test_the_whole_loop_to_merged(self):
        with patch.dict(os.environ, self.env):
            j = tasks.TasksJournal()
            tid = j.emit("task.explained", {"title": "T", "text": "Monta o relatório"}, actor="gabriel")["task_id"]
            self.assertEqual(j.read({"id": tid})["status"], "explained")
            j.emit("understanding.taught_back", {"text": "vou montar"}, tid)
            j.emit("understanding.confirmed", {"text": "bate"}, tid)
            status = lambda: j.read({"id": tid})["status"]  # noqa: E731
            tasks.execute(tid, cwd=str(self.repo))
            self.assertEqual(status(), "executed")
            self.verdict(True)
            tasks.verify(tid)
            self.assertEqual(status(), "verified")
            tasks.deliver(tid, "pr", url="https://github.com/o/r/pull/9", text="PR aberto")
            self.assertEqual(status(), "delivered")
            self.assertEqual(j.read({"id": tid})["delivery"], {"text": "PR aberto", "kind": "pr", "url": "https://github.com/o/r/pull/9"})
            # the Human asked for a review first: back to execution
            tasks.request_review(tid, "falta o caso do mês sem vendas")
            state = j.read({"id": tid})
            self.assertEqual((state["status"], state["review_requests"], state["delivery"]),
                             ("confirmed", ["falta o caso do mês sem vendas"], None))
            tasks.execute(tid, cwd=str(self.repo))
            self.assertIn("falta o caso do mês sem vendas", self.calls()[-1][-1])  # the next run is told why
            self.verdict(True)
            tasks.verify(tid)
            tasks.deliver(tid, "pr", url="https://github.com/o/r/pull/9")
            merged = tasks.merge(tid)
            self.assertEqual((merged["event"], merged["value"]["url"]), ("pull_request.merged", "https://github.com/o/r/pull/9"))
            self.assertEqual(status(), "merged")
            with self.assertRaisesRegex(ValueError, "merged"):
                tasks.merge(tid)  # recorded once
            history = j.read({"id": tid, "history": True})
            self.assertEqual([e["event"] for e in history], [
                "task.explained", "understanding.taught_back", "understanding.confirmed", "task.executed",
                "task.verified", "task.delivered", "pull_request.review_requested", "task.executed", "task.verified",
                "task.delivered", "pull_request.merged"])
            x, _ = tasks.outcome_of(history)  # the last run: its own verification and delivery, not the first one's
            self.assertEqual((x.verification.passed, x.delivered.kind, x.delivered.url),
                             (True, "pr", "https://github.com/o/r/pull/9"))
            # every transition the loop took is drawn in the graph
            for a, b in [("task.executed", "task.verified"), ("task.verified", "task.delivered"),
                         ("task.verified", "task.executed"), ("task.delivered", "pull_request.merged"),
                         ("task.delivered", "pull_request.review_requested"), ("pull_request.review_requested", "task.executed")]:
                self.assertIn(b, tasks.TRANSITIONS[a])

    def test_cli_verify_deliver_merge(self):
        with patch.dict(os.environ, self.env):
            j, tid, _ = self.start()
        self.verdict(True)
        env = {**os.environ, **self.env}
        script = str(Path(tasks.__file__))

        def cli(*argv):
            done = subprocess.run([sys.executable, script, *argv], env=env, capture_output=True, text=True, cwd=self.repo)
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(done.stdout)

        self.assertTrue(cli("verify", "--task", tid, "--model", "glm")["value"]["passed"])
        self.assertEqual(cli("deliver", "--task", tid, "--kind", "pr", "--url", "https://x/pr/1")["value"]["kind"], "pr")
        self.assertEqual(cli("merge", "--task", tid)["event"], "pull_request.merged")
        done = subprocess.run([sys.executable, script, "request-review", "--task", tid, "--text", "x"], env=env,
                              capture_output=True, text=True, cwd=self.repo)
        self.assertNotEqual(done.returncode, 0)  # merged already: the decision is taken

    def test_parse_verdict(self):
        pv = tasks.parse_verdict
        nested = 'x {"passed": true, "checks": [{"what": "a", "passed": false}]} y'
        self.assertEqual(pv(nested)["passed"], True)  # the checks' own "passed" never wins over the verdict
        self.assertEqual(pv('{"passed": false}\ntext\n```json\n{"passed": true, "checks": []}\n```')["passed"], True)
        self.assertIsNone(pv("no json here {not json}"))
        self.assertIsNone(pv('{"checks": []}'))

    def test_result_from_and_projector_keep_older_events(self):
        j = tasks.TasksJournal()
        tid = j.emit("task.explained", {"title": "T", "text": "t"})["task_id"]
        j.emit("understanding.taught_back", {"text": "r"}, tid)
        j.emit("understanding.confirmed", {"text": "ok"}, tid)
        j.emit("task.executed", {"text": "feito", "exit_code": 0, "worktree": "/w", "branch": "b"}, tid)
        x, run = tasks.outcome_of(j.read({"id": tid, "history": True}))
        self.assertEqual((x.verification, x.delivered, x.branch), (None, None, "b"))
        state = j.read({"id": tid})
        self.assertEqual((state["status"], state["verification"], state["delivery"], state["review_requests"]),
                         ("executed", None, None, []))
        self.assertEqual(tasks.outcome_of([]), (None, None))


FAKE_GH = r'''#!/bin/sh
# fake gh: reads canned answers from $FAKE_GH_DIR; never touches GitHub.
d="$FAKE_GH_DIR"
if [ "$1 $2" = "pr list" ]; then
  head=; state=
  while [ $# -gt 0 ]; do
    case "$1" in --head) head="$2";; --state) state="$2";; esac
    shift
  done
  f="$d/pr-$state-$(printf %s "$head" | tr / _).json"
  if [ -f "$f" ]; then cat "$f"; else echo '[]'; fi
  exit 0
fi
if [ "$1 $2" = "pr view" ]; then cat "$d/view.json"; exit 0; fi
echo "fake gh: unexpected $*" >&2; exit 2
'''
FAKE_WT = r'''#!/bin/sh
# fake wt: remove <branch> --foreground = remove its worktree, then delete the branch only when merged (-d)
branch="$2"
git merge-base --is-ancestor "$branch" main || { echo "wt: $branch is not merged" >&2; exit 1; }
path="$(git worktree list --porcelain | awk -v b="refs/heads/$branch" '/^worktree /{w=$2} $0=="branch " b {print w}')"
[ -n "$path" ] && git worktree remove "$path" || exit 1
git branch -d "$branch" >/dev/null 2>&1 || exit 1
'''


class Clean(RepoCase):
    """workspace.cleaned: `clean` checks the worktree, the remote branch and the PR with real git and a fake gh."""

    def setUp(self):
        super().setUp()
        git = lambda *a, cwd=self.repo: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)  # noqa: E731
        self.git = git
        self.origin = self.home / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True, capture_output=True)
        git("branch", "-M", "main")
        git("remote", "add", "origin", str(self.origin))
        git("push", "-q", "origin", "main")
        self.gh_dir = self.home / "gh-answers"
        self.gh_dir.mkdir()
        for name, body in (("gh", FAKE_GH), ("wt", FAKE_WT)):
            f = self.home / name
            f.write_text(body, encoding="utf-8")
            f.chmod(0o755)
        self.env = {**self.env, "TASKS_GH": str(self.home / "gh"), "TASKS_WT": str(self.home / "wt"),
                    "FAKE_GH_DIR": str(self.gh_dir)}

    def merged_task(self, branch: str | None = None):
        """A task merged through a PR from a branch with its worktree, pushed to origin; returns (journal, id, branch, worktree)."""
        with patch.dict(os.environ, self.env):
            j = tasks.TasksJournal()
            tid = j.emit("task.explained", {"title": "T", "text": "t"})["task_id"]
            branch = branch or tasks.branch_name(tid, "feito")
            wt = self.home / "wt-feito"
            self.git("worktree", "add", "-q", str(wt), "-b", branch)
            (wt / "a.txt").write_text("a", encoding="utf-8")
            self.git("add", ".", cwd=wt)
            self.git("commit", "-qm", "work", cwd=wt)
            self.git("push", "-q", "origin", branch, cwd=wt)
            self.git("merge", "-q", "--ff-only", branch)  # merged into main (a squash would need wt's own check)
            self.git("push", "-q", "origin", "main")
            j.emit("understanding.taught_back", {"text": "r"}, tid)
            j.emit("understanding.confirmed", {"text": "ok"}, tid)
            j.emit("task.executed", {"text": "feito", "exit_code": 0, "worktree": str(wt), "branch": branch}, tid)
            j.emit("task.verified", {"text": "ok", "passed": True, "checks": []}, tid)
            tasks.deliver(tid, "pr", url="https://github.com/o/r/pull/9")
            tasks.merge(tid)
            (self.gh_dir / f"pr-merged-{branch.replace('/', '_')}.json").write_text('[{"number": 9}]', encoding="utf-8")
            (self.gh_dir / "view.json").write_text(json.dumps({"headRefName": branch}), encoding="utf-8")
        return j, tid, branch, wt

    def test_branch_names_carry_the_task_id(self):
        tid = "0123456789ab"
        self.assertEqual(tasks.branch_name(tid, "Sonnet"), "task/01234567-sonnet")
        self.assertEqual(tasks.branch_name(tid, "Fix the Bug!"), "task/01234567-fix-the-bug")
        with self.assertRaises(ValueError):
            tasks.branch_name(tid, "  ")

    def test_clean_removes_and_records_after_the_merge(self):
        j, tid, branch, wt = self.merged_task()
        self.assertEqual(j.read({"id": tid})["status"], "merged")  # merged is not done yet
        with patch.dict(os.environ, self.env):
            ev = tasks.clean(tid, repo=str(self.repo))
        self.assertEqual(ev["event"], "workspace.cleaned")
        self.assertEqual((ev["value"]["branch"], ev["value"]["pr_url"], ev["value"]["worktree"]),
                         (branch, "https://github.com/o/r/pull/9", str(wt)))
        self.assertEqual(ev["value"]["repo"], str(self.repo))
        self.assertEqual(j.read({"id": tid})["status"], "done")
        self.assertFalse(wt.exists())
        self.assertEqual(self.git("ls-remote", "--heads", "origin", branch).stdout.decode().strip(), "")
        self.assertIn("workspace.cleaned", tasks.TRANSITIONS["pull_request.merged"])

    def test_clean_refuses_what_is_not_clean_and_records_nothing(self):
        j, tid, branch, wt = self.merged_task()
        (self.gh_dir / f"pr-open-{branch.replace('/', '_')}.json").write_text('[{"number": 10}]', encoding="utf-8")
        with patch.dict(os.environ, self.env):
            with self.assertRaisesRegex(ValueError, "open PR"):
                tasks.clean(tid, repo=str(self.repo))  # the worktree went, the PR is still open: not clean
        self.assertEqual(j.read({"id": tid})["status"], "merged")
        self.assertNotIn("workspace.cleaned", [e["event"] for e in j.read({"id": tid, "history": True})])

    def test_clean_never_deletes_a_remote_branch_without_a_merged_pr(self):
        j, tid, branch, wt = self.merged_task()
        (self.gh_dir / f"pr-merged-{branch.replace('/', '_')}.json").unlink()
        with patch.dict(os.environ, self.env):
            with self.assertRaisesRegex(ValueError, "no merged PR"):
                tasks.clean(tid, repo=str(self.repo))
        self.assertIn(branch, self.git("ls-remote", "--heads", "origin", branch).stdout.decode())

    def test_clean_refuses_a_worktree_with_unmerged_work(self):
        j, tid, branch, wt = self.merged_task()
        (wt / "b.txt").write_text("b", encoding="utf-8")
        self.git("add", ".", cwd=wt)
        self.git("commit", "-qm", "more", cwd=wt)  # a commit main does not have: wt (never forced) refuses
        with patch.dict(os.environ, self.env):
            with self.assertRaisesRegex(ValueError, "refused"):
                tasks.clean(tid, repo=str(self.repo))
        self.assertTrue(wt.exists())

    def test_clean_needs_a_merge_first_and_cli_merge_prints_the_command(self):
        with patch.dict(os.environ, self.env):
            j = tasks.TasksJournal()
            tid = j.emit("task.explained", {"title": "T", "text": "t"})["task_id"]
            j.emit("understanding.taught_back", {"text": "r"}, tid)
            j.emit("understanding.confirmed", {"text": "ok"}, tid)
            j.emit("task.executed", {"text": "feito", "exit_code": 0, "worktree": "/w", "branch": "b"}, tid)
            j.emit("task.verified", {"text": "ok", "passed": True, "checks": []}, tid)
        env = {**os.environ, **self.env}
        script = str(Path(tasks.__file__))
        run = lambda *a: subprocess.run([sys.executable, script, *a], env=env, capture_output=True, text=True, cwd=self.repo)  # noqa: E731
        done = run("clean", "--task", tid, "--repo", str(self.repo))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("pull_request.merged", done.stderr)
        self.assertEqual(run("deliver", "--task", tid, "--kind", "pr", "--url", "https://x/pr/1").returncode, 0)
        merged = run("merge", "--task", tid)
        self.assertEqual(merged.returncode, 0, merged.stderr)
        self.assertIn(f"tasks.sh clean --task {tid}", merged.stderr)
        self.assertEqual(json.loads(merged.stdout)["event"], "pull_request.merged")  # stdout stays JSON
        self.assertEqual(run("branch", "--task", tid, "--slug", "x").stdout.strip(), f"task/{tid[:8]}-x")

if __name__ == "__main__":
    unittest.main()
