#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["nats-py>=2.9"]
# ///
"""Read-only timeline of agent events from a NATS JetStream stream.

Config (env): NATS_URL (default nats://127.0.0.1:4222), POSTMORTEM_STREAM
(default: found by subject), POSTMORTEM_SUBJECT_PREFIX (default: all subjects).
Subject grammar assumed: <prefix>.<domain>.<entity>.<event>; payload is JSON.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import nats
from nats.js.api import ConsumerConfig, DeliverPolicy, AckPolicy
from nats.errors import TimeoutError as NatsTimeout

TURN_KEYS = ("turn_id", "turn")
TRACE_KEYS = ("trace_id", "conversation_id", "gen_ai.conversation.id")
ACTOR_KEYS = ("actor", "agent", "agent_name", "author", "user", "source")
TIME_KEYS = ("ts", "time", "timestamp", "at")
USED_KEYS = ("path", "file", "url", "query", "command", "cmd", "input", "args", "read", "text", "prompt", "card")
GEN_KEYS = ("result", "output", "effect", "choice", "response", "outcome")
SHORT_SKIP = set(TURN_KEYS + TRACE_KEYS + ACTOR_KEYS + TIME_KEYS)


def parse_time(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s / 1000 if s > 1e11 else s, timezone.utc)
    s = str(s)
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return datetime.now(timezone.utc) - timedelta(**{{"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}[u]: n})
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def first(d, keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def short(v, n=60):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def to_event(msg):
    try:
        p = json.loads(msg.data.decode())
    except Exception:
        p = {"raw": msg.data.decode(errors="replace")}
    if not isinstance(p, dict):
        p = {"value": p}
    body = p.get("data") if isinstance(p.get("data"), dict) else {}
    flat = {**body, **{k: v for k, v in p.items() if k != "data"}}
    t = parse_time(first(flat, TIME_KEYS)) or msg.metadata.timestamp.astimezone(timezone.utc)
    return {
        "time": t,
        "seq": msg.metadata.sequence.stream,
        "subject": msg.subject,
        "actor": first(flat, ACTOR_KEYS),
        "turn": first(flat, TURN_KEYS),
        "trace": first(flat, TRACE_KEYS),
        "fields": flat,
        "raw": msg.data.decode(errors="replace"),
    }


async def fetch(args):
    nc = await nats.connect(os.environ.get("NATS_URL", "nats://127.0.0.1:4222"))
    js = nc.jetstream()
    prefix = os.environ.get("POSTMORTEM_SUBJECT_PREFIX", "").strip(".")
    subj = f"{prefix}.>" if prefix else ">"
    stream = os.environ.get("POSTMORTEM_STREAM") or await js.find_stream_name_by_subject(subj if prefix else ">")
    since = parse_time(args.since)
    cfg = ConsumerConfig(
        deliver_policy=DeliverPolicy.BY_START_TIME if since else DeliverPolicy.ALL,
        opt_start_time=since.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if since else None,
        ack_policy=AckPolicy.EXPLICIT,
        filter_subject=subj,
        inactive_threshold=30,
    )
    sub = await js.pull_subscribe(subj, stream=stream, config=cfg)
    out = []
    while True:
        try:
            msgs = await sub.fetch(256, timeout=1.5)
        except NatsTimeout:
            break
        for m in msgs:
            out.append(to_event(m))
            await m.ack()
    await nc.close()
    return out


def select(events, args):
    until = parse_time(args.until)
    since = parse_time(args.since)
    ev = [e for e in events if (not since or e["time"] >= since) and (not until or e["time"] <= until)]
    needles = [x for x in (args.card, args.turn, args.trace) if x]
    if not needles:
        return ev
    hit = [e for e in ev if any(n in e["raw"] for n in needles)]
    turns = {e["turn"] for e in hit if e["turn"]}
    traces = {e["trace"] for e in hit if e["trace"]}
    if args.card:  # a card names a request; follow its turns and traces
        return [e for e in ev if e in hit or e["turn"] in turns or e["trace"] in traces]
    return [e for e in ev if e in hit or (args.trace and e["trace"] in traces) or (args.turn and e["turn"] in turns)]


def line(e):
    f = {k: v for k, v in e["fields"].items() if k not in SHORT_SKIP}
    kv = " ".join(f"{k}={short(v)}" for k, v in list(f.items())[:5])
    return f"{e['time'].astimezone().strftime('%H:%M:%S')}  {e['subject']}  {e['actor'] or '-'}  {kv}".rstrip()


def render_text(events):
    groups = {}
    for e in sorted(events, key=lambda e: (e["time"], e["seq"])):
        groups.setdefault(e["turn"] or "-", []).append(e)
    out = []
    for turn, evs in groups.items():
        out.append(f"== turn {turn} ({len(evs)} events) ==")
        out += ["  " + line(e) for e in evs]
    return "\n".join(out)


def render_prov(events):
    agents, entities, acts = {}, {}, []
    for e in sorted(events, key=lambda e: (e["time"], e["seq"])):
        aid = f"agent:{e['actor']}" if e["actor"] else None
        if aid:
            agents.setdefault(aid, {"@type": "prov:Agent", "id": aid})
        used, gen = [], []
        for k, v in e["fields"].items():
            if k in USED_KEYS or k in GEN_KEYS:
                eid = f"entity:{k}:{short(v, 80)}"
                entities.setdefault(eid, {"@type": "prov:Entity", "id": eid, "kind": k, "value": v})
                (gen if k in GEN_KEYS else used).append(eid)
        acts.append({
            "@type": "prov:Activity",
            "id": f"activity:{e['seq']}",
            "type": e["subject"],
            "startedAtTime": e["time"].isoformat(),
            "wasAssociatedWith": aid,
            "turn_id": e["turn"],
            "trace_id": e["trace"],
            "used": used,
            "generated": gen,
        })
    return {"activities": acts, "entities": list(entities.values()), "agents": list(agents.values())}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--card"), ap.add_argument("--turn"), ap.add_argument("--trace")
    ap.add_argument("--since", help="ISO time or 30m/2h/1d")
    ap.add_argument("--until", help="ISO time")
    ap.add_argument("--json", action="store_true", help="PROV-like JSON")
    args = ap.parse_args()
    events = select(asyncio.run(fetch(args)), args)
    if not events:
        print("no events matched", file=sys.stderr)
        return 1
    print(json.dumps(render_prov(events), ensure_ascii=False, indent=2) if args.json else render_text(events))
    return 0


if __name__ == "__main__":
    sys.exit(main())
