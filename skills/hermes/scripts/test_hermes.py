#!/usr/bin/env python3
"""Tests for hermes.sh against a fake `hermes` binary: no model is ever called.

Run: python3 skills/hermes/scripts/test_hermes.py
"""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SH = Path(__file__).with_name("hermes.sh")

FAKE = r'''#!/usr/bin/env bash
# fake hermes: profile list, -z (echo + usage file), sessions, peer dm
args=("$@")
if [ "${args[0]}" = "profile" ]; then
cat <<'EOT'
 Profile          Model                        Gateway      Alias        Distribution
 ───────────────    ───────────────────────────    ───────────    ───────────    ────────────────────
  default         gpt-5.5                      running      —            —
 ◆bili            claude-opus-5-5              running      —            —
  researcher      claude-opus-5-5              running      researcher   —
  cheap           glm-4.5                      running      —            —
EOT
exit 0
fi
if [ "${args[0]}" = "peer" ]; then echo "peer says hi to ${args[2]}"; exit 0; fi
[ "${args[0]}" = "-p" ] || exit 9
shift 2
if [ "$1" = "sessions" ]; then
  if [ "$2" = "list" ]; then echo "Title  ID"; echo "x  sess-1 limit=$4"; exit 0; fi
  if [ "$2" = "export" ]; then
    out="${@: -1}"; mkdir -p "$out"; printf '# session\n%s\n' "$(printf 'line %.0s' $(seq 1 3000))" > "${out}s.md"; exit 0
  fi
fi
resume=""; task=""; usage=""
while [ $# -gt 0 ]; do
  case "$1" in
    --resume) resume="$2"; shift 2;;
    -z) task="$2"; shift 2;;
    --usage-file) usage="$2"; shift 2;;
    *) shift;;
  esac
done
[ -n "${FAKE_SLEEP:-}" ] && sleep "$FAKE_SLEEP"
echo "answer to: $task (cwd $(basename "$PWD"))"
[ -n "$usage" ] && echo '{"session_id":"sess-42","input_tokens":7,"api_key":"SHOULD-NOT-SHOW"}' > "$usage"
exit "${FAKE_EXIT:-0}"
'''


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        (t / "bin").mkdir()
        fake = t / "bin" / "hermes"
        fake.write_text(FAKE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        root = t / "root"
        for name, provider in (("researcher", "claude-subscription-directsdk-experimental"), ("cheap", "openrouter"),
                               ("bili", "zai-coding-plan")):
            d = root / "profiles" / name
            d.mkdir(parents=True)
            (d / "config.yaml").write_text(f"model:\n  default: m\n  provider: {provider}\nchat_model:\n  provider: openrouter\n")
            (d / "SOUL.md").write_text(f"# {name}\n\nYou are {name}, does things.\n")
        (root / "profiles" / "researcher" / "memories").mkdir()
        (root / "profiles" / "researcher" / "memories" / "MEMORY.md").write_text("remembered\n")
        (root / "config.yaml").write_text("model:\n  default: gpt-5.5\n  provider: openai-codex\n")
        self.env = {**os.environ, "HERMES_BIN": str(fake), "HERMES_ROOT": str(root),
                    "HERMES_SKILL_STATE": str(t / "state"), "PATH": f"{t / 'bin'}:{os.environ['PATH']}"}
        self.t = t

    def tearDown(self):
        self.tmp.cleanup()

    def sh(self, *args, env=None):
        return subprocess.run(["bash", str(SH), *args], capture_output=True, text=True, env={**self.env, **(env or {})}, cwd=self.tmp.name)

    def test_list_parsing(self):
        r = self.sh("list", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {p["profile"]: p for p in json.loads(r.stdout)}
        self.assertEqual(set(rows), {"default", "bili", "researcher", "cheap"})
        self.assertEqual(rows["researcher"]["model"], "claude-opus-5-5")
        self.assertEqual(rows["researcher"]["description"], "You are researcher, does things.")
        self.assertTrue(rows["researcher"]["flat"])
        self.assertTrue(rows["default"]["flat"])  # openai-codex
        self.assertFalse(rows["cheap"]["flat"])  # chat_model's openrouter must not leak into the model's provider
        self.assertIn("REFUSED", self.sh("list").stdout)

    def test_spawn_json_line_and_cwd(self):
        work = self.t / "proj"
        work.mkdir()
        r = self.sh("spawn", "researcher", "find x", "--cwd", str(work))
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[0], "answer to: find x (cwd proj)")
        last = json.loads(lines[-1])
        self.assertEqual((last["profile"], last["session_id"], last["exit_code"]), ("researcher", "sess-42", 0))
        self.assertIn("duration_s", last)
        self.assertEqual(last["usage"]["input_tokens"], 7)
        self.assertNotIn("api_key", last["usage"])  # never echo secrets
        self.assertNotIn("SHOULD-NOT-SHOW", r.stdout + r.stderr)
        self.assertFalse((self.t / "state" / "locks" / "researcher").exists())  # released

    def test_lock_second_spawn_exits_3(self):
        lock = self.t / "state" / "locks" / "researcher"
        lock.mkdir(parents=True)
        (lock / "pid").write_text(str(os.getppid()))  # a live pid that is not us
        r = self.sh("spawn", "researcher", "again")
        self.assertEqual(r.returncode, 3)
        self.assertIn("busy", r.stderr)
        (lock / "pid").write_text("999999")  # dead pid: stale lock is taken over
        self.assertEqual(self.sh("spawn", "researcher", "again").returncode, 0)

    def test_spawn_of_the_code_profile_checks_the_wip_limit(self):
        fake = self.t / "kanban.sh"
        fake.write_text('#!/bin/sh\necho "$@" > "$KLOG"\necho "o/r: 3 open PR(s), limit 3"\nexit "${KEXIT:-0}"\n')
        fake.chmod(0o755)
        env = {"HERMES_KANBAN": str(fake), "KLOG": str(self.t / "klog")}
        r = self.sh("spawn", "hacker", "x", "--repo", "o/r", env={**env, "KEXIT": "3"})
        self.assertEqual(r.returncode, 6)
        self.assertIn("WIP limit reached", r.stderr)
        self.assertEqual((self.t / "klog").read_text().strip(), "wip --repo o/r")
        # no refusal when there is room, a failing check only warns (the profile is unknown here: 5 proves it got past)
        self.assertEqual(self.sh("spawn", "hacker", "x", "--repo", "o/r", env={**env, "KEXIT": "0"}).returncode, 5)
        r = self.sh("spawn", "hacker", "x", "--repo", "o/r", env={**env, "KEXIT": "1"})
        self.assertEqual(r.returncode, 5)
        self.assertIn("warning", r.stderr)
        # other profiles and spawns without --repo are never checked
        (self.t / "klog").unlink()
        self.sh("spawn", "researcher", "x", "--repo", "o/r", env={**env, "KEXIT": "3"})
        self.sh("spawn", "hacker", "x", env={**env, "KEXIT": "3"})
        self.assertFalse((self.t / "klog").exists())

    def test_per_token_profile_refused(self):
        r = self.sh("spawn", "cheap", "x")
        self.assertEqual(r.returncode, 4)
        self.assertIn("openrouter", r.stderr)
        self.assertEqual(self.sh("spawn", "nobody", "x").returncode, 5)
        self.assertEqual(self.sh("sessions", "cheap").returncode, 4)

    def test_route_table(self):
        for kind, profile in (("research", "researcher"), ("ui", "hipster"), ("css", "hipster"), ("infra", "sre"),
                              ("ads", "via-ads"), ("search", "via-ads"), ("disk", "mantainer"), ("coordination", "bili")):
            self.assertEqual(self.sh("route", kind).stdout.strip(), profile, kind)
        self.assertEqual(self.sh("route", "code").stdout.strip(), "hacker")
        r = self.sh("route", "poetry")
        self.assertEqual(r.returncode, 1)
        self.assertIn("subagent", r.stderr)

    def test_exit_code_mapping(self):
        for code in (1, 2, 130):
            r = self.sh("spawn", "researcher", "x", env={"FAKE_EXIT": str(code)})
            self.assertEqual(r.returncode, code)
            self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1])["exit_code"], code)
            self.assertIn("not a success", r.stderr)

    def test_timeout_is_124(self):
        r = self.sh("spawn", "researcher", "x", "--timeout", "1", env={"FAKE_SLEEP": "5"})
        self.assertEqual(r.returncode, 124)
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1])["exit_code"], 124)

    def test_resume_sessions_read_memory_dm(self):
        r = self.sh("resume", "researcher", "sess-9", "more")
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1])["exit_code"], 0)
        self.assertIn("limit=3", self.sh("sessions", "researcher", "--limit", "3").stdout)
        out = self.sh("read", "researcher", "sess-1", "--max-chars", "400").stdout
        self.assertIn("trimmed", out)
        self.assertLess(len(out), 700)
        self.assertIn("remembered", self.sh("memory", "researcher").stdout)
        self.assertEqual(self.sh("dm", "researcher", "hi").returncode, 64)  # only when the owner asked
        self.assertIn("peer says hi", self.sh("dm", "researcher", "hi", "--owner-asked").stdout)


FAKE_WS = r'''#!/usr/bin/env bash
# fake hermes for workspace: sessions live in $WS/sessions (tab: title, workspace, id), calls logged in $WS/log
args=("$@")
echo "$*" >> "$WS/log"
if [ "${args[0]}" = "profile" ]; then
  printf ' Profile Model Gateway Alias Distribution\n ◆bili   m   running  —  —\n'; exit 0
fi
shift 2
if [ "$1" = "sessions" ] && [ "$2" = "list" ]; then
  echo "Title                        Workspace          Last Active   ID"
  echo "──────────────────────────────────────────────────────────────"
  while IFS=$'\t' read -r t w i; do printf '%-28s %-18s %-13s %s\n' "$t" "$w" "just now" "$i"; done < "$WS/sessions"
  exit 0
fi
if [ "$1" = "sessions" ] && [ "$2" = "rename" ]; then printf '%s\t%s\t%s\n' "$4" repo "$3" >> "$WS/sessions"; exit 0; fi
usage=""
while [ $# -gt 0 ]; do case "$1" in --usage-file) usage="$2"; shift 2;; *) shift;; esac; done
[ -n "$usage" ] && echo '{"session_id":"local-new1"}' > "$usage"
echo answer
'''

FAKE_TMUX = r'''#!/usr/bin/env bash
echo "$*" >> "$WS/tmuxlog"
case "$1" in
  has-session) grep -qx "${3#=}" "$WS/tmux.sessions" 2>/dev/null;;
  new-session) echo "$4" >> "$WS/tmux.sessions";;
esac
'''


class WorkspaceTest(unittest.TestCase):
    """workspace: the Hermes session and the tmux session named slug; reused when they exist, never duplicated."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        for name, body in (("hermes", FAKE_WS), ("tmux", FAKE_TMUX)):
            (t / name).write_text(body)
            (t / name).chmod(0o755)
        (t / "repo").mkdir()
        (t / "sessions").write_text("")
        root = t / "root" / "profiles" / "bili"
        root.mkdir(parents=True)
        (root / "config.yaml").write_text("model:\n  default: m\n  provider: zai-coding-plan\n")
        self.t = t
        self.env = {**os.environ, "HERMES_BIN": str(t / "hermes"), "TMUX_BIN": str(t / "tmux"), "WS": str(t),
                    "HERMES_ROOT": str(t / "root"), "HERMES_SKILL_STATE": str(t / "state")}

    def tearDown(self):
        self.tmp.cleanup()

    def ws(self, *extra):
        r = subprocess.run(["bash", str(SH), "workspace", "sygnal-0-2", "--repo", str(self.t / "repo"), *extra],
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_creates_then_reuses(self):
        first = self.ws("--context", "start here")
        self.assertEqual((first["session"], first["tmux"], first["session_id"]), ("created", "created", "local-new1"))
        log = (self.t / "log").read_text()
        self.assertIn("-p bili --in", log)
        self.assertIn("start here", log)
        self.assertIn("sessions rename local-new1 sygnal-0-2", log)
        self.assertIn("sygnal-0-2", (self.t / "tmuxlog").read_text())
        again = self.ws("--context", "start here")
        self.assertEqual((again["session"], again["tmux"], again["session_id"]), ("reused", "reused", "local-new1"))
        self.assertEqual(log.count("-z"), (self.t / "log").read_text().count("-z"))  # no second first-context run

    def test_context_file_and_bad_slug(self):
        (self.t / "ctx.md").write_text("from a file\n")
        self.ws("--context-file", str(self.t / "ctx.md"))
        self.assertIn("from a file", (self.t / "log").read_text())
        r = subprocess.run(["bash", str(SH), "workspace", "Bad Slug", "--repo", str(self.t / "repo")], capture_output=True,
                           text=True, env=self.env)
        self.assertEqual(r.returncode, 64)


if __name__ == "__main__":
    unittest.main()
