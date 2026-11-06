# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""shape: the journal of the planning door. One shaping is one request walked through context, routing, backbrief and
delegation (Shape Up: shape the work before betting on it). Drawn in the dev-console as the Shape domain.

The journal is a global append-only JSONL, ~/.local/share/shape/events.jsonl (override SHAPE_DIR); the only writer is
`emit` here (through shape.sh).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

EVENTS = {
    "request": {
        # O dono pediu algo (construir, escrever, mudar, decidir): nasce uma modelagem.
        "receive": "received",
    },
    "piece": {
        # A peça de planejamento escolhida pelo tipo do pedido (ou direct, quando o pedido é claro e pequeno).
        "route": "routed",
    },
    "understanding": {
        # O backbrief: o agente repetiu o pedido ao dono com as próprias palavras. Espera o ok dele.
        "teach_back": "taught_back",
        # O dono confirmou (ou corrigiu): só agora se constrói.
        "confirm": "confirmed",
        # Ao 2º ajuste do dono (a 3ª tentativa) abre-se uma linha de entendimento em vez de chutar de novo.
        "open_line": "line_opened",
    },
    "backbrief": {
        # n conta os teach-backs deste pedido (1, 2); a 3ª tentativa não existe: vira understanding.line_opened.
        "attempt": "attempted",
    },
    "work": {
        # O trabalho saiu: subagente (minutos), thread (tópico que vive) ou card no Upstream.
        "delegate": "delegated",
    },
    "resources": {
        # A escolha do menor custo: "Decidi X porque Y", com a estimativa de minutos e de R$.
        "choose": "chosen",
    },
    "shaping": {
        # A modelagem terminou: o real (minutos, R$) alimenta o `learn`.
        "close": "closed",
    },
}

TRANSITIONS = {
    "request.received": ["piece.routed"],
    "piece.routed": ["understanding.taught_back"],
    "understanding.taught_back": ["backbrief.attempted", "understanding.line_opened", "understanding.taught_back",
                                  "understanding.confirmed"],
    "backbrief.attempted": ["understanding.taught_back", "understanding.line_opened"],
    "understanding.line_opened": ["understanding.taught_back", "understanding.confirmed"],
    "understanding.confirmed": ["resources.chosen", "work.delegated"],
    "resources.chosen": ["work.delegated", "shaping.closed"],
    "work.delegated": ["resources.chosen", "shaping.closed"],
}

MAX_ATTEMPTS = 2  # teach-backs before the line opens
LINE_TOOLS = ("clarify", "interview")

PIECES = ("brainstorm", "pelo-resultado", "interview", "domain-plan", "design-taste", "direct")
DELEGATIONS = ("subagent", "thread", "card")


def _project(events: list[dict]) -> dict:
    """A shaping as the journal leaves it: the request, the piece, how far it got, the attempts, the cost."""
    if not events:
        return {}
    s = {"id": events[-1]["shaping"], "request": "", "piece": "", "status": "received", "delegated_to": "",
         "attempts": 0, "line": "", "resources": [], "est_minutes": None, "est_cost_brl": None,
         "real_minutes": None, "real_cost_brl": None, "updated_at": events[-1]["at"]}
    for e in events:
        v = e.get("value", {})
        kind = e["event"]
        if kind == "request.received":
            s["request"] = v.get("text", "")
        elif kind == "piece.routed":
            s["piece"] = v.get("piece", "")
        elif kind == "understanding.taught_back":
            s["attempts"] = max(s["attempts"], 1)
        elif kind == "backbrief.attempted":
            s["attempts"] = max(s["attempts"], v.get("n", 0))
        elif kind == "understanding.line_opened":
            s["line"] = v.get("tool", "")
        elif kind == "work.delegated":
            s["delegated_to"] = v.get("to", "")
        elif kind == "resources.chosen":
            s.update(resources=v["resources"], est_minutes=v["est_minutes"], est_cost_brl=v["est_cost_brl"])
        elif kind == "shaping.closed":
            s.update(real_minutes=v["real_minutes"], real_cost_brl=v["real_cost_brl"])
        s["status"] = kind.split(".")[1]
    return s


class ShapeJournal:
    """Read-only view of the Shape journal for the dev-console contract."""

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        events = _all_events()
        if "id" in query:
            matches = [e for e in events if e.get("shaping") == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        return shapings()


def journal_path() -> Path:
    """The journal, read from SHAPE_DIR on every call."""
    return Path(os.environ.get("SHAPE_DIR", "~/.local/share/shape")).expanduser() / "events.jsonl"


def _all_events() -> list[dict]:
    p = journal_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _num(value: dict, *keys: str) -> None:
    for k in keys:
        if isinstance(value.get(k), bool) or not isinstance(value.get(k), (int, float)) or value[k] < 0:
            raise ValueError(f"value.{k} must be a number >= 0")


def validate(event: str, value: dict, history: list[dict] | None = None) -> None:
    history = history or []
    if event == "piece.routed":
        if value.get("piece") not in PIECES:
            raise ValueError(f"value.piece must be one of {PIECES}")
    elif event == "work.delegated":
        if value.get("to") not in DELEGATIONS:
            raise ValueError(f"value.to must be one of {DELEGATIONS}")
    elif event == "backbrief.attempted":
        n = value.get("n")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("value.n must be an integer >= 1")
        if n > MAX_ATTEMPTS:
            raise ValueError(f"attempt {n} does not exist: after {MAX_ATTEMPTS} teach-backs open the line "
                             f"(understanding.line_opened, tool one of {LINE_TOOLS}) instead of guessing again")
    elif event == "understanding.line_opened":
        if value.get("tool") not in LINE_TOOLS:
            raise ValueError(f"value.tool must be one of {LINE_TOOLS}")
        got = max([e["value"].get("n", 0) for e in history if e["event"] == "backbrief.attempted"] or [0])
        if got < MAX_ATTEMPTS:
            raise ValueError(f"the line opens on the owner's {MAX_ATTEMPTS}nd adjustment: only {got} attempt(s) so far")
    elif event == "resources.chosen":
        r = value.get("resources")
        if not isinstance(r, list) or not r or not all(isinstance(x, str) for x in r):
            raise ValueError("value.resources must be a non-empty list of catalog names")
        _num(value, "est_minutes", "est_cost_brl")
        if not value.get("why"):
            raise ValueError("value needs `why` (Decidi X porque Y)")
    elif event == "shaping.closed":
        _num(value, "real_minutes", "real_cost_brl")
    elif not value.get("text"):
        raise ValueError("value needs a non-empty `text`")


def emit(event: str, value: dict, shaping: str, actor: str = "agent") -> dict:
    valid = {f"{d}.{k}" for d, kinds in EVENTS.items() for k in kinds.values()}
    if event not in valid:
        raise ValueError(f"unknown event {event!r}; one of {sorted(valid)}")
    if not isinstance(value, dict):
        raise ValueError("value must be a JSON object")
    if not shaping:
        raise ValueError(f"{event} requires --shaping <id>")
    validate(event, value, [e for e in _all_events() if e.get("shaping") == shaping])
    row: dict[str, Any] = {"id": uuid.uuid4().hex[:12], "event": event, "shaping": shaping,
                           "at": datetime.now().astimezone().isoformat(timespec="seconds"), "actor": actor,
                           "value": value}
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def shapings(status: str | None = None) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for e in _all_events():
        if e.get("shaping"):
            groups.setdefault(e["shaping"], []).append(e)
    out = [s for g in groups.values() if (s := _project(g))]
    return [s for s in out if not status or s["status"] == status]


def catalog_path() -> Path:
    """resources.json, next to the skill (SHAPE_CATALOG overrides it, for tests)."""
    if os.environ.get("SHAPE_CATALOG"):
        return Path(os.environ["SHAPE_CATALOG"]).expanduser()
    return Path(__file__).resolve().parent.parent / "references" / "resources.json"


def load_catalog() -> dict:
    return json.loads(catalog_path().read_text())


def choose(kind: str, catalog: dict | None = None) -> dict:
    """The least-cost combination for a request kind: per slot, the cheapest option (R$, then minutes)."""
    cat = catalog or load_catalog()
    kinds = cat["request_kinds"]
    if kind not in kinds:
        raise ValueError(f"unknown request kind {kind!r}; one of {sorted(kinds)}")
    res, picked, dropped = cat["resources"], [], []
    for slot, options in kinds[kind]["slots"].items():
        if not options:
            continue
        ranked = sorted(options, key=lambda o: (res[o]["est_cost_brl"], res[o]["est_minutes"]))
        picked.append(ranked[0])
        dropped += [f"{o} (R$ {res[o]['est_cost_brl']:.2f})" for o in ranked[1:]]
    minutes = round(sum(res[r]["est_minutes"] for r in picked), 1)
    cost = round(sum(res[r]["est_cost_brl"] for r in picked), 2)
    why = f"é o menor custo estimado para '{kind}' ({kinds[kind]['what']}): R$ {cost:.2f} em {minutes} min"
    if dropped:
        why += "; descartei " + ", ".join(dropped)
    return {"resources": picked, "est_minutes": minutes, "est_cost_brl": cost, "why": why}


def _blend(old: float, ratio: float, alpha: float) -> float:
    return old * (1 + alpha * (min(max(ratio, 0.1), 10) - 1))


def learn(catalog: dict | None = None) -> tuple[dict, list[str]]:
    """Estimated vs real, per resource of every shaping closed since the last learn: a moving average
    (alpha) pulls each estimate toward what it really took. Returns (new catalog, diff lines)."""
    cat = catalog or load_catalog()
    alpha, seen = cat["learn"]["alpha"], cat["learn"]["closed_seen"]
    events = _all_events()
    closed = [e for e in events if e["event"] == "shaping.closed"]
    diff: list[str] = []
    for c in closed[seen:]:
        chosen = [e for e in events if e["event"] == "resources.chosen" and e["shaping"] == c["shaping"]
                  and e["at"] <= c["at"]]
        if not chosen:
            continue
        est, real = chosen[-1]["value"], c["value"]
        for name in est["resources"]:
            r = cat["resources"].get(name)
            if not r:
                continue
            for field, ek, rk in (("est_minutes", "est_minutes", "real_minutes"),
                                  ("est_cost_brl", "est_cost_brl", "real_cost_brl")):
                if est[ek] > 0:
                    old = r[field]
                    r[field] = round(_blend(old, real[rk] / est[ek], alpha), 1 if field == "est_minutes" else 2)
                    if r[field] != old:
                        diff.append(f"{name} {field}: {old} -> {r[field]}  (shaping {c['shaping']}: "
                                    f"est {est[ek]} vs real {real[rk]})")
            r["learned_n"] = r.get("learned_n", 0) + 1
            r["source"] = f"journal:~/.local/share/shape/events.jsonl n={r['learned_n']}" if \
                r["source"] == "estimate" or r["source"].startswith("journal:~/.local/share/shape/") else \
                r["source"].split(" + shape")[0] + f" + shape n={r['learned_n']}"
    cat["learn"]["closed_seen"] = len(closed)
    return cat, diff


def open_pr(path: Path, diff: list[str]) -> str:
    """The learned catalog goes to a PR (gh-app, a worktree of its own), never straight to main."""
    import shutil
    import subprocess
    from datetime import datetime as dt
    repo = subprocess.check_output(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"], text=True).strip()
    branch = "learn/shape-" + dt.now().strftime("%Y%m%d-%H%M%S")
    wt = f"{repo}.{branch.replace('/', '-')}"

    def run(*a: str, cwd: str = repo) -> str:
        return subprocess.run(a, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()
    run("wt", "switch", "-c", branch, "--base", "origin/main", "--no-cd")
    try:
        dest = Path(wt) / path.relative_to(repo)
        shutil.copy(path, dest)
        run("gh-app", "git-config", cwd=wt)
        run("git", "add", str(dest), cwd=wt)
        run("git", "commit", "-m", "shape: learn (resources.json from real numbers)", cwd=wt)
        run("gh-app", "push", "-u", "origin", branch, cwd=wt)
        body = "`shape.sh learn`: estimates moved toward the real numbers of the closed shapings.\n\n" + \
            "\n".join(f"- {d}" for d in diff)
        url = run("gh-app", "pr", "create", "--repo", "biliboss/skills", "--base", "main", "--head", branch,
                  "--title", "shape: learn, resources.json from real numbers", "--body", body, cwd=wt)
    finally:
        run("wt", "remove", "--foreground", branch)
    return url


def run_learn(pr: bool = True) -> list[str]:
    cat, diff = learn()
    path = catalog_path()
    path.write_text(json.dumps(cat, ensure_ascii=False, indent=1) + "\n")
    print("\n".join(diff) if diff else "learn: nothing to change")
    if diff and pr and os.environ.get("SHAPE_LEARN_PR") != "0":
        print(f"learn: PR {open_pr(path, diff)}")
    return diff


def maybe_autolearn() -> None:
    """Every `learn.every` (10) closed shapings since the last learn, learn without being asked."""
    cat = load_catalog()
    if len([e for e in _all_events() if e["event"] == "shaping.closed"]) - cat["learn"]["closed_seen"] >= cat["learn"]["every"]:
        print("learn: 10 shapings closed since the last learn, running it")
        run_learn()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shape.py", description="Shape journal: the only writer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("event")
    e.add_argument("value")
    e.add_argument("--shaping", required=True)
    e.add_argument("--actor", required=True)
    s = sub.add_parser("list")
    s.add_argument("--status")
    c = sub.add_parser("choose", help="least-cost combination of the catalog for a request kind")
    c.add_argument("kind")
    c.add_argument("--shaping", help="also emit resources.chosen for this shaping")
    c.add_argument("--actor", default="agent")
    ln = sub.add_parser("learn", help="rewrite resources.json from estimated vs real (the --learn modifier)")
    ln.add_argument("--no-pr", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            print(json.dumps(emit(a.event, json.loads(a.value), a.shaping, a.actor), ensure_ascii=False))
            if a.event == "shaping.closed":
                maybe_autolearn()
        elif a.cmd == "choose":
            pick = choose(a.kind)
            print("Decidi " + " + ".join(pick["resources"]) + " porque " + pick["why"] + ".")
            if a.shaping:
                emit("resources.chosen", pick, a.shaping, a.actor)
        elif a.cmd == "learn":
            run_learn(pr=not a.no_pr)
        else:
            print(json.dumps(shapings(a.status), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    except Exception as ex:  # a failing PR step: the catalog is already rewritten, say so
        print(f"error: {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
