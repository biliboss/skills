# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of auth: fake gws and envless on PATH, a temp HOME. Run: uv run --script test_auth.py
The real Keychain, vault and journal are never touched; a canary secret must never reach any output or file."""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SH = str(Path(__file__).parent / "auth.sh")
CANARY = "CANARY-SECRET-123"

FAKE_ENVLESS = """#!/bin/sh
case "$1" in
  list) cat "$FAKE_VAULT_KEYS" 2>/dev/null ;;
  set) echo "$2" >> "$FAKE_VAULT_KEYS"; cat >> "$FAKE_VAULT_VALUES" ;;
  exec) while [ "$1" != "--" ]; do shift; done; shift; exec "$@" ;;
esac
"""
FAKE_GWS = """#!/bin/sh
d="$GOOGLE_WORKSPACE_CLI_CONFIG_DIR"
case "$1 $2" in
  "auth status") if [ -f "$d/token" ]; then echo '{"auth_method":"oauth2","storage":"encrypted"}'; else echo '{"auth_method":"none","storage":"none"}'; fi ;;
  "auth login") echo "$@" > "$d/login_args"; echo ok > "$d/token" ;;
  "auth logout") rm -f "$d/token" ;;
  *) if [ "$(cat "$d/token" 2>/dev/null)" = expired ]; then echo '{"error":{"code":401,"reason":"authError","message":"invalid_grant"}}'; exit 1; fi
     echo "gws-ran $* in $(pwd) as $d" ;;
esac
"""


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        (t / "bin").mkdir()
        for n, body in (("envless", FAKE_ENVLESS), ("gws", FAKE_GWS)):
            (t / "bin" / n).write_text(body)
            (t / "bin" / n).chmod(0o755)
        (t / "cofre" / ".envless").mkdir(parents=True)
        self.env = {**os.environ, "HOME": str(t), "PATH": f"{t / 'bin'}:{os.environ['PATH']}", "AUTH_HOME": str(t / "cfg"),
                    "AUTH_DIR": str(t / "share"), "FAKE_VAULT_KEYS": str(t / "keys"), "FAKE_VAULT_VALUES": str(t / "vals")}
        for k in ("AUTH_PROFILE", "HERMES_HOME"):
            self.env.pop(k, None)
        self.t = t

    def sh(self, *args, env=None, stdin=None):
        return subprocess.run([SH, *args], env={**self.env, **(env or {})}, capture_output=True, text=True, input=stdin)

    def journal(self):
        p = self.t / "share" / "events.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def setup_ready(self):
        (self.t / "keys").write_text("GOOGLE_WORKSPACE_CLI_CLIENT_ID\nGOOGLE_WORKSPACE_CLI_CLIENT_SECRET\n")
        return self.sh("setup", "google", "--cofre", str(self.t / "cofre"))

    def test_setup_without_client_stops_with_console_steps(self):
        r = self.sh("setup", "google", "--cofre", str(self.t / "cofre"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("console.cloud.google.com/apis/credentials", r.stdout)
        self.assertEqual(self.journal(), [])

    def test_setup_stores_client_from_json_by_stdin_and_never_prints_it(self):
        f = self.t / "client_secret.json"
        f.write_text(json.dumps({"installed": {"client_id": "id-1", "client_secret": CANARY}}))
        r = self.sh("setup", "google", "--cofre", str(self.t / "cofre"), "--client-secret-json", str(f))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(CANARY, r.stdout + r.stderr)
        self.assertIn(CANARY, (self.t / "vals").read_text())  # reached the vault through stdin
        self.assertNotIn(CANARY, (self.t / "cfg" / "config.json").read_text())
        self.assertNotIn(CANARY, (self.t / "share" / "events.jsonl").read_text())
        self.assertEqual(self.journal()[0]["event"], "provider.updated")

    def test_add_login_check_flow_and_journal(self):
        self.setup_ready()
        r = self.sh("add", "google", "pessoal", "a@x.com", "--services", "calendar")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.t / ".config" / "gws" / "contas" / "a@x.com"
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)
        r = self.sh("check", "pessoal")
        self.assertEqual(r.returncode, 1)
        self.assertIn("precisa de login", r.stdout)
        self.assertEqual(self.sh("login", "pessoal").returncode, 0)
        self.assertIn("--readonly", (d / "login_args").read_text())
        r = self.sh("check", "--json")
        self.assertTrue(json.loads(r.stdout)[0]["ok"])
        kinds = [e["event"] for e in self.journal()]
        self.assertEqual(kinds.count("account.connected"), 1)
        self.assertIn("account.checked", kinds)
        self.assertIn("● ok", self.sh("list").stdout)

    def test_expired_token_needs_login_not_broken(self):
        self.setup_ready()
        self.sh("add", "google", "p", "a@x.com")
        self.sh("login", "p")
        (self.t / ".config/gws/contas/a@x.com/token").write_text("expired")
        r = self.sh("check", "p", "--json")
        self.assertEqual(json.loads(r.stdout)[0]["status"], "needs_login")

    def test_profile_grant_gate(self):
        self.setup_ready()
        self.sh("add", "google", "p", "a@x.com")
        self.sh("login", "p")
        r = self.sh("run", "p", "--", "gws", "calendar", "x", env={"AUTH_PROFILE": "hacker"})
        self.assertEqual(r.returncode, 4)
        self.assertIn("grant p --profile hacker", r.stderr)
        self.assertEqual(self.sh("grant", "p", "--profile", "hacker").returncode, 0)
        r = self.sh("run", "p", "--", "gws", "calendar", "x", env={"AUTH_PROFILE": "hacker"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gws-ran calendar x", r.stdout)
        self.sh("revoke", "p", "--profile", "hacker")
        self.assertEqual(self.sh("run", "p", "--", "gws", "x", env={"AUTH_PROFILE": "hacker"}).returncode, 4)
        self.assertEqual(self.sh("aliases", env={"AUTH_PROFILE": "hipster"}).stdout, "")
        self.assertEqual(self.sh("aliases").stdout.strip(), "p")

    def test_hermes_home_names_the_profile(self):
        self.setup_ready()
        self.sh("add", "google", "p", "a@x.com")
        r = self.sh("run", "p", "--", "gws", "x", env={"HERMES_HOME": "/h/.hermes/profiles/hacker"})
        self.assertEqual(r.returncode, 4)

    def test_run_keeps_the_callers_folder(self):
        self.setup_ready()
        self.sh("add", "google", "p", "a@x.com")
        self.sh("login", "p")
        here = Path(self.tmp.name) / "work"
        here.mkdir()
        r = subprocess.run([SH, "run", "p", "--", "gws", "z"], cwd=here, env=self.env, capture_output=True, text=True)
        self.assertIn(os.path.realpath(here), os.path.realpath(r.stdout.split(" in ")[1].split(" as ")[0]))

    def test_remove_needs_confirmation_and_is_local_only(self):
        self.setup_ready()
        self.sh("add", "google", "p", "a@x.com")
        self.sh("login", "p")
        r = self.sh("remove", "p")
        self.assertEqual(r.returncode, 3)
        self.assertTrue((self.t / ".config/gws/contas/a@x.com/token").exists())
        r = self.sh("remove", "p", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.t / ".config/gws/contas/a@x.com").exists())
        last = self.journal()[-2]
        self.assertEqual((last["event"], last["value"]["revoked_remotely"]), ("account.disconnected", False))
        self.assertEqual(json.loads(self.sh("list", "--json").stdout), [])

    def test_journal_refuses_secret_looking_keys(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        os.environ["AUTH_DIR"] = str(self.t / "share")
        import auth
        with self.assertRaises(ValueError):
            auth.emit("provider.updated", {"client_secret": "x"})


if __name__ == "__main__":
    unittest.main()
