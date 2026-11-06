# /// script
# requires-python = ">=3.10"
# dependencies = ["watchfiles>=0.21"]
# ///
"""Tests of console_agents.py: the normalizer and the tailer, on invented lines only (never a real log).
Run: uv run --script test_console_agents.py   (stdlib unittest, a temp dir as the root)"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import console_agents as ca  # noqa: E402

SRC = ca.SOURCES["claude"]


def fs_for(name="abcdef12-0000.jsonl"):
    return ca.FileState(Path("/x/proj") / name, "k1", "claude", name[:8], "proj", name.startswith("agent-"))


def line(**kw):
    base = {"type": "user", "timestamp": "2026-01-02T03:04:05.000Z", "cwd": "/w/demo", "isSidechain": False}
    base.update(kw)
    return json.dumps(base).encode()


def norm(raw, off=0, fs=None):
    return SRC.normalize(raw, off, fs or fs_for())


class NormalizerTest(unittest.TestCase):
    def test_typed_string_is_a_prompt(self):
        e = norm(line(message={"content": "hello"}, origin={"kind": "human"}, promptSource="typed", turnOrigin="human"), 42)
        self.assertEqual((e["kind"], e["text"], e["more"], e["id"], e["project"], e["session"]), ("prompt", "hello", False, "k1:42", "demo", "abcdef12"))

    def test_typed_without_turn_origin_is_still_a_prompt(self):
        self.assertEqual(norm(line(message={"content": "x"}, origin={"kind": "human"}, promptSource="typed"))["kind"], "prompt")

    def test_typed_array_with_image_shows_text_and_a_marker(self):
        content = [{"type": "text", "text": "look"}, {"type": "image", "source": {}}]
        e = norm(line(message={"content": content}, origin={"kind": "human"}, promptSource="typed"))
        self.assertEqual((e["kind"], e["text"]), ("prompt", "look\n[image]"))

    def test_peer_and_task_notification_have_their_own_kinds(self):
        e = norm(line(message={"content": "raw"}, origin={"kind": "peer", "name": "other", "body": "hi"}, promptSource="system"))
        self.assertEqual((e["kind"], e["text"]), ("cross", "other: hi"))
        e = norm(line(message={"content": "done"}, origin={"kind": "task-notification"}, promptSource="system"))
        self.assertEqual((e["kind"], e["text"]), ("notification", "done"))

    def test_allow_list_unknown_goes_to_other_never_prompt(self):
        for extra in ({}, {"origin": {"kind": "human"}}, {"origin": {"kind": "human"}, "promptSource": "queued"},
                      {"origin": {"kind": "weird"}, "promptSource": "typed"}, {"promptSource": "typed"}):
            e = norm(line(message={"content": "x"}, **extra))
            self.assertEqual(e["kind"], "other", extra)

    def test_tool_result_user_lines_are_noise(self):
        self.assertIsNone(norm(line(message={"content": [{"type": "tool_result", "content": "x"}]})))

    def test_sidechain_and_agent_files_are_flagged(self):
        self.assertTrue(norm(line(message={"content": "x"}, isSidechain=True, origin={"kind": "human"}, promptSource="typed"))["side"])
        self.assertTrue(norm(line(message={"content": "x"}, origin={"kind": "human"}, promptSource="typed"), fs=fs_for("agent-abc123.jsonl"))["side"])

    def test_assistant_text_and_tool_use(self):
        e = norm(line(type="assistant", message={"content": [{"type": "text", "text": "ok"}, {"type": "tool_use", "name": "Bash"}]}))
        self.assertEqual((e["kind"], e["text"]), ("assistant", "ok"))
        e = norm(line(type="assistant", message={"content": [{"type": "tool_use", "name": "Bash"}, {"type": "tool_use", "name": "Read"}]}))
        self.assertEqual((e["kind"], e["text"]), ("tool", "Bash, Read"))

    def test_noise_types_are_dropped(self):
        for t in ("attachment", "api-request", "last-prompt", "permission-mode", "mode"):
            self.assertIsNone(norm(line(type=t)))

    def test_text_is_clipped_and_full_on_demand(self):
        raw = line(message={"content": "a" * 1000}, origin={"kind": "human"}, promptSource="typed")
        e = norm(raw)
        self.assertEqual((len(e["text"]), e["more"]), (ca.SHORT, True))
        self.assertEqual(len(SRC.normalize(raw, 0, fs_for(), full=True)["text"]), 1000)

    def test_a_line_above_one_megabyte_is_skipped(self):
        big = b'{"type":"api-request-blob","blob":"' + b"x" * (ca.MAX_LINE + 10) + b'"}'
        self.assertIsNone(norm(big))
        big_user = line(message={"content": "y" * (ca.MAX_LINE + 10)}, origin={"kind": "human"}, promptSource="typed")
        self.assertIsNone(norm(big_user))

    def test_garbled_and_truncated_lines_do_not_raise(self):
        for raw in (b'{"type":"user","message":{"cont', b"not json", b"[1,2]", b"", b"null", b'{"type":"user","message":5}'):
            self.assertIsNone(norm(raw))


def typed(text, ts="2026-01-02T03:04:05.000Z"):
    return line(message={"content": text}, origin={"kind": "human"}, promptSource="typed", timestamp=ts) + b"\n"


class TailerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "proj").mkdir()
        self.f = self.root / "proj" / "11112222-aaaa.jsonl"
        self.f.write_bytes(typed("one"))
        self.hub = ca.Hub([self.root])
        self.hub.rescan()
        self.hub.backfill()

    def texts(self):
        return [e["text"] for e in self.hub.get_prompts()["entries"]]

    def bump(self):  # make sure mtime differs even on a coarse clock
        st = self.f.stat()
        os.utime(self.f, (st.st_atime, st.st_mtime + 2))

    def test_backfill_reads_the_existing_tail(self):
        self.assertEqual(self.texts(), ["one"])

    def test_append_gives_exactly_one_new_entry(self):
        seq = self.hub.cur_seq()
        with open(self.f, "ab") as fh:
            fh.write(typed("two"))
        self.assertEqual(self.hub.tick(), 1)
        self.assertEqual(self.hub.tick(), 0)
        self.assertEqual(self.texts(), ["one", "two"])
        self.assertEqual([e["text"] for e in self.hub.since(seq)], ["two"])

    def test_partial_last_line_waits_for_its_newline(self):
        whole = typed("three")
        with open(self.f, "ab") as fh:
            fh.write(whole[:30])
        self.assertEqual(self.hub.tick(), 0)
        with open(self.f, "ab") as fh:
            fh.write(whole[30:-1])
        self.bump()
        self.assertEqual(self.hub.tick(), 0)  # still no trailing newline
        with open(self.f, "ab") as fh:
            fh.write(b"\n")
        self.assertEqual(self.hub.tick(), 1)
        self.assertEqual(self.texts(), ["one", "three"])

    def test_garbled_line_in_the_middle_is_skipped(self):
        with open(self.f, "ab") as fh:
            fh.write(b'{"type":"user","mess\n' + typed("after"))
        self.assertEqual(self.hub.tick(), 1)
        self.assertEqual(self.texts(), ["one", "after"])

    def test_shrinking_file_resets_and_says_so(self):
        with open(self.f, "ab") as fh:
            fh.write(typed("two"))
        self.hub.tick()
        seq = self.hub.cur_seq()
        self.f.write_bytes(typed("new"))  # rewritten, shorter
        self.bump()
        self.hub.tick()
        self.assertEqual(self.texts(), ["new"])
        marks = [e for e in self.hub.since(seq) if e["kind"] == "reset"]
        self.assertEqual(len(marks), 1)

    def test_new_file_is_picked_up_on_rescan(self):
        g = self.root / "other" / "33334444-bbbb.jsonl"
        g.parent.mkdir()
        g.write_bytes(typed("fresh"))
        self.assertEqual(self.hub.tick(), 0)  # not known yet
        self.hub.rescan()
        self.assertEqual(self.hub.tick(), 1)
        self.assertEqual(self.texts(), ["one", "fresh"])
        self.assertIn("33334444", [s["session"] for s in self.hub.sessions()])

    def test_disappearing_file_keeps_the_past_and_does_not_raise(self):
        self.f.unlink()
        self.hub.tick()
        self.assertEqual(self.texts(), ["one"])

    def test_symlinked_root_is_deduplicated(self):
        link = Path(self.tmp.name + "-link")
        link.symlink_to(self.root)
        self.addCleanup(link.unlink)
        os.environ[ca.ENV_DIRS] = os.pathsep.join([str(self.root), str(link)])
        self.addCleanup(os.environ.pop, ca.ENV_DIRS)
        self.assertEqual(len(ca.roots_from_env()), 1)

    def test_prompts_filters_and_side_default(self):
        with open(self.f, "ab") as fh:
            fh.write(line(message={"content": "peer"}, origin={"kind": "peer"}, promptSource="system") + b"\n")
            fh.write(line(message={"content": "sub"}, origin={"kind": "human"}, promptSource="typed", isSidechain=True) + b"\n")
        self.hub.tick()
        self.assertEqual(self.texts(), ["one"])
        self.assertEqual([e["text"] for e in self.hub.get_prompts(kinds=("cross",))["entries"]], ["peer"])
        self.assertEqual([e["text"] for e in self.hub.get_prompts(side=True)["entries"]], ["one", "sub"])
        self.assertEqual(self.hub.get_prompts(session="zzz")["entries"], [])

    def test_entry_full_text_by_id_and_unknown_ids(self):
        long = "z" * 2000
        with open(self.f, "ab") as fh:
            fh.write(typed(long))
        self.hub.tick()
        e = self.hub.get_prompts()["entries"][-1]
        self.assertTrue(e["more"])
        self.assertEqual(len(self.hub.get_entry(e["id"])["text"]), 2000)
        self.assertIsNone(self.hub.get_entry("nokey:0"))
        self.assertIsNone(self.hub.get_entry("../../etc/passwd"))

    def test_seq_of_resumes_after_an_id(self):
        first = self.hub.last_id()
        with open(self.f, "ab") as fh:
            fh.write(typed("two"))
        self.hub.tick()
        s = self.hub.seq_of(first)
        self.assertEqual([e["text"] for e in self.hub.since(s)], ["two"])
        self.assertIsNone(self.hub.seq_of("gone:1"))


class LiveTest(unittest.TestCase):
    """The hub running its own thread: events (watchfiles) as the trigger; polling when the import fails."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "proj").mkdir()
        self.f = self.root / "proj" / "55556666-cccc.jsonl"
        self.f.write_bytes(typed("seed"))

    def start(self):
        hub = ca.Hub([self.root])
        t = threading.Thread(target=hub.run, daemon=True)
        t.start()
        self.addCleanup(lambda: (hub.stop(), t.join(3)))
        self.assertTrue(hub.ready.wait(5))
        return hub

    def wait_for(self, hub, text, limit=3.0):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < limit:
            if any(e.get("text") == text for e in hub.since(0)):
                return time.perf_counter() - t0
            time.sleep(0.005)
        return None

    def test_append_arrives_by_event_fast(self):
        hub = self.start()
        time.sleep(0.5)  # the watcher is up
        self.assertEqual(hub.mode, "watch")
        with open(self.f, "ab") as fh:
            fh.write(typed("live"))
        dt = self.wait_for(hub, "live")
        print(f"\n  append -> hub: {dt * 1000:.0f} ms" if dt else "\n  append never arrived")
        self.assertIsNotNone(dt)
        self.assertLess(dt, 0.3)

    def test_new_file_in_a_new_folder_is_picked_up(self):
        hub = self.start()
        time.sleep(0.5)
        (self.root / "newdir").mkdir()
        (self.root / "newdir" / "77778888-dddd.jsonl").write_bytes(typed("born"))
        dt = self.wait_for(hub, "born")
        self.assertIsNotNone(dt)
        self.assertLess(dt, 1.0)

    def test_polling_fallback_when_watchfiles_cannot_be_imported(self):
        saved = sys.modules.get("watchfiles", "absent")
        sys.modules["watchfiles"] = None  # makes `from watchfiles import watch` raise ImportError
        try:
            hub = self.start()
            time.sleep(0.2)
            self.assertEqual(hub.mode, "poll")
            self.assertEqual(hub.get_log()["mode"], "poll")
            with open(self.f, "ab") as fh:
                fh.write(typed("polled"))
            self.assertIsNotNone(self.wait_for(hub, "polled", 3.0))
        finally:
            if saved == "absent":
                sys.modules.pop("watchfiles", None)
            else:
                sys.modules["watchfiles"] = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
