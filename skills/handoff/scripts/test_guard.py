# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for the handoff-guard hooks: fake payloads, temp git repos. Run: uv run scripts/test_guard.py"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin" / "handoff-guard" / "__init__.py"


@pytest.fixture
def guard(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("handoff_guard", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("HANDOFF_GUARD_STATE", str(tmp_path / "state"))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.chdir(repo)
    monkeypatch.delenv("TERMINAL_CWD", raising=False)
    mod.repo = repo
    return mod


def usage(g, sid, pct, window=1_000_000):
    g.record_usage(session_id=sid, usage={"prompt_tokens": int(window * pct / 100)}, context_length=window)


def ask(g, sid="s1", msg="keep going"):
    return g.check(session_id=sid, user_message=msg)


def test_no_key_does_nothing(guard):
    usage(guard, "s1", 99)
    assert ask(guard) is None


def test_below_threshold(guard):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=60\n")
    usage(guard, "s1", 59)
    assert ask(guard) is None


def test_at_threshold_injects_once(guard):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=60\n")
    usage(guard, "s1", 61)
    first = ask(guard)
    assert "context" in first and "--from s1 --detach" in first["context"] and "handoff.sh" in first["context"]
    assert ask(guard) is None


def test_reinjects_after_dropping_below(guard):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=60\n")
    usage(guard, "s1", 61)
    assert ask(guard) is not None
    usage(guard, "s1", 10)
    assert ask(guard) is None
    usage(guard, "s1", 62)
    assert ask(guard) is not None


def test_blocks_at_plus_15(guard):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=60\n")
    usage(guard, "s1", 75)
    r = ask(guard)
    assert r["action"] == "block" and "--from s1 --detach" in r["message"]
    assert ask(guard)["action"] == "block"   # blocks every turn, not once


def test_handoff_message_is_not_blocked(guard):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=60\n")
    usage(guard, "s1", 80)
    r = ask(guard, msg="faz o handoff")
    assert r is None or "action" not in r


def test_wiki_config_wins_over_biliboss(guard):
    (guard.repo / ".wiki").mkdir()
    (guard.repo / ".wiki" / "wiki.config").write_text('WIKI_LANG=en\nHANDOFF_AT="50"\n')
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=90\n")
    assert guard.threshold() == 50


def test_subfolder_reads_toplevel(guard, monkeypatch):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=40\n")
    sub = guard.repo / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert guard.threshold() == 40


def test_outside_repo(guard, tmp_path, monkeypatch):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=10\n")
    usage(guard, "s1", 99)
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert ask(guard) is None


def test_bad_value_and_no_usage_and_garbage(guard):
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=abc\n")
    usage(guard, "s1", 99)
    assert ask(guard) is None
    (guard.repo / ".biliboss").write_text("HANDOFF_AT=60\n")
    assert ask(guard, sid="never-called") is None   # no API call yet: no number
    usage(guard, "s1", 99)
    assert guard.check() is None and guard.check(session_id="s1", user_message=None)["action"] == "block"


def test_register(guard):
    seen = []

    class Ctx:
        def register_hook(self, name, fn):
            seen.append(name)

    guard.register(Ctx())
    assert seen == ["post_api_request", "pre_llm_call"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
