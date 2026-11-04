#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["nats-py>=2.9"]
# ///
"""Tests on a throwaway nats-server (random port, temp store); never the real one."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import nats

HERE = os.path.dirname(os.path.abspath(__file__))
CARD, TURN, TRACE = "CARD-42", "turn-7", "trace-abc"

FIXTURE = [
    ("mesa.agent.request.received", {"ts": "2026-11-04T10:00:00Z", "actor": "user", "card": CARD, "turn_id": TURN, "trace_id": TRACE, "text": "apaga os logs antigos"}),
    ("mesa.agent.turn.started", {"ts": "2026-11-04T10:00:01Z", "actor": "agent-a", "turn_id": TURN, "trace_id": TRACE}),
    ("mesa.agent.tool.called", {"ts": "2026-11-04T10:00:02Z", "actor": "agent-a", "turn_id": TURN, "trace_id": TRACE, "tool": "read", "path": "/var/log/README"}),
    ("mesa.agent.tool.called", {"ts": "2026-11-04T10:00:03Z", "actor": "agent-a", "turn_id": TURN, "trace_id": TRACE, "tool": "bash", "command": "rm -rf /var/log/*"}),
    ("mesa.agent.decision.made", {"ts": "2026-11-04T10:00:04Z", "actor": "agent-a", "turn_id": TURN, "trace_id": TRACE, "card": CARD, "choice": "delete all", "why": "'antigos' read as 'all'"}),
    ("mesa.agent.turn.finished", {"ts": "2026-11-04T10:00:05Z", "actor": "agent-a", "turn_id": TURN, "trace_id": TRACE, "result": "deleted"}),
    ("mesa.agent.turn.started", {"ts": "2026-11-04T10:30:00Z", "actor": "agent-b", "turn_id": "turn-other", "trace_id": "trace-zzz"}),
]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def seed(url):
    nc = await nats.connect(url)
    js = nc.jetstream()
    await js.add_stream(name="EV", subjects=["mesa.>"])
    for subj, p in FIXTURE:
        await js.publish(subj, json.dumps(p).encode())
    await nc.close()


class Timeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.store = tempfile.TemporaryDirectory()
        cls.srv = subprocess.Popen(
            ["nats-server", "-js", "-a", "127.0.0.1", "-p", str(cls.port), "-sd", cls.store.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.url = f"nats://127.0.0.1:{cls.port}"
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        asyncio.run(seed(cls.url))

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait()
        cls.store.cleanup()

    def run_tl(self, *a):
        env = {**os.environ, "NATS_URL": self.url, "POSTMORTEM_STREAM": "EV", "POSTMORTEM_SUBJECT_PREFIX": "mesa"}
        r = subprocess.run([sys.executable, os.path.join(HERE, "timeline.py"), *a], env=env, capture_output=True, text=True, timeout=60)
        return r

    def test_card_groups_by_turn_and_includes_decision(self):
        r = self.run_tl("--card", CARD, "--since", "2026-11-04T09:00:00Z")
        self.assertEqual(r.returncode, 0, r.stderr)
        print("\n" + r.stdout)
        self.assertIn(f"== turn {TURN} (6 events) ==", r.stdout)
        self.assertIn("mesa.agent.decision.made", r.stdout)
        self.assertIn("choice=delete all", r.stdout)
        self.assertNotIn("turn-other", r.stdout)

    def test_window_until(self):
        r = self.run_tl("--trace", TRACE, "--since", "2026-11-04T09:00:00Z", "--until", "2026-11-04T10:00:02Z")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count("mesa.agent"), 3)

    def test_turn_json_prov(self):
        r = self.run_tl("--turn", TURN, "--json", "--since", "2026-11-04T09:00:00Z")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(len(d["activities"]), 6)
        self.assertEqual({a["id"] for a in d["agents"]}, {"agent:user", "agent:agent-a"})
        dec = [a for a in d["activities"] if a["type"].endswith("decision.made")][0]
        self.assertEqual(dec["wasAssociatedWith"], "agent:agent-a")
        self.assertTrue(any(e["kind"] == "choice" for e in d["entities"]))
        self.assertTrue(any(e["kind"] == "command" for e in d["entities"]))

    def test_no_match(self):
        r = self.run_tl("--card", "NOPE-1", "--since", "2026-11-04T09:00:00Z")
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
