#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""domain-plan: the plan of a task while its card is in Upstream, and the drift between the drawing and the code.

The plan is a JSONL in the project's repo, `<repo>/.plan/<slug>.jsonl`, editable by hand (one JSON per line,
`{id, event, at, actor, value}`, like every journal of the house):

    plan.started     {slug, domain, events_file, console_source}
                                                      the plan opened; `events_file` is the Python file whose EVENTS
                                                      literal says what the code records (read with ast, the REAL
                                                      registry); `console_source` is the file the dev-console reads as
                                                      SOURCE: the real file plus the draft events, rewritten by plan.sh
                                                      after every change (the console reads EVENTS with ast)
    element.updated  {kind, name, state, ...}         one event covers create, change and delete (change: deleted)
                                                      kind event    {command, after}   name "category.event"
                                                      kind screen   {event, file|url}  the real screen above an event
                                                      kind document {text, sources, questions, decisions}
                                                      state draft | real
    plan.confirmed   {by}                             the owner approved: Downstream builds the drift list

    plan.sh start   <slug> [--repo R] [--domain D] [--events-file F] [--console-source F]
    plan.sh add     <slug> --kind event|screen|document --name N [--state draft|real] [...]
    plan.sh show    <slug> [--json]
    plan.sh drift   <slug> [--mark] [--json] [--detailed-exitcode]
    plan.sh sync    <slug>                     # rewrite the console's SOURCE (after editing the JSONL by hand)
    plan.sh confirm <slug> [--by owner]

Drift = `terraform plan` for a task: desired (the drawing) against actual (the code) -> what to apply.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("event", "screen", "document")
STATES = ("draft", "real")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
WORD = re.compile(r"^[a-z][a-z0-9_]*$")  # a category, a command or an event: it is written into Python source


def plan_path(repo: str | Path, slug: str) -> Path:
    if not SLUG.match(slug):
        raise ValueError(f"slug must be lowercase words joined by '-': {slug!r}")
    return Path(repo).expanduser() / ".plan" / f"{slug}.jsonl"


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(path: Path, event: str, value: dict, actor: str = "agent") -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    e = {"id": uuid.uuid4().hex, "event": event, "at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
         "actor": actor, "value": value}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e


def project(events: list[dict]) -> dict:
    """Fold the journal: the header, the elements (last update wins, deleted leaves) and whether it was confirmed."""
    state = {"slug": None, "domain": None, "events_file": None, "console_source": None, "elements": {}, "confirmed": False}
    for e in events:
        v = e.get("value") or {}
        if e["event"] == "plan.started":
            state.update(slug=v.get("slug"), domain=v.get("domain"), events_file=v.get("events_file"),
                          console_source=v.get("console_source"), confirmed=False)
        elif e["event"] == "element.updated":
            key = (v["kind"], v["name"])
            if v.get("change") == "deleted":
                state["elements"].pop(key, None)
            else:
                state["elements"][key] = {**state["elements"].get(key, {}), **v}
        elif e["event"] == "plan.confirmed":
            state["confirmed"] = True
    return state


def registry(path: Path) -> list[str]:
    """['category.event'] from the EVENTS literal of a Python file, read with ast (never imported), as the dev-console reads it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EVENTS" for t in node.targets):
            try:
                reg = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                return []
            return [f"{c}.{ev}" for c, cmds in reg.items() if isinstance(cmds, dict) for ev in cmds.values()]
    return []


def _reachable(el: dict, repo: Path) -> bool:
    if el.get("file"):
        return (repo / el["file"]).expanduser().exists()
    if str(el.get("url", "")).startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(el["url"], method="HEAD")
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status < 400
        except Exception:
            return False
    return False


def drift(state: dict, repo: str | Path) -> dict:
    """The three groups (to_build, built, unplanned) plus `lost` (marked real, gone from the code) and the documents."""
    repo = Path(repo).expanduser()
    ef = state.get("events_file")
    code = None
    if ef:
        p = Path(ef).expanduser()
        code = set(registry(p if p.is_absolute() else repo / p))
    out = {"to_build": [], "built": [], "unplanned": [], "lost": [], "documents": [], "events_read": code is not None}
    drawn = set()
    for (kind, name), el in sorted(state["elements"].items()):
        item = {"kind": kind, "name": name}
        if kind == "document":
            out["documents"].append({**item, "questions": el.get("questions", []), "decisions": el.get("decisions", []),
                                     "sources": el.get("sources", [])})
            continue
        if kind == "event":
            drawn.add(name)
            if code is None:
                continue
            exists = name in code
        else:
            exists = _reachable(el, repo)
        if el.get("state", "draft") == "real":
            if not exists:
                out["lost"].append(item)
        elif exists:
            out["built"].append(item)
        else:
            out["to_build"].append(item)
    if code is not None:
        out["unplanned"] = [{"kind": "event", "name": n} for n in sorted(code - drawn)]
    return out


def render_source(real: str, state: dict) -> str:
    """The real registry's file with the draft events written into its EVENTS literal, each commented as a draft (the
    console reads EVENTS from SOURCE with ast, so a draft only shows when the file says it). Needs the closing brace of
    EVENTS (and of an existing category) on a line of its own, as the house writes them."""
    have = set()
    tree = ast.parse(real)
    node = next((n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EVENTS" for t in n.targets)), None)
    if node is None or not isinstance(node.value, ast.Dict):
        raise ValueError("the events file has no EVENTS dict literal")
    cats = {k.value: v for k, v in zip(node.value.keys, node.value.values) if isinstance(k, ast.Constant)}
    for c, v in cats.items():
        have |= {f"{c}.{x.value}" for x in getattr(v, "values", []) if isinstance(x, ast.Constant)}
    drafts: dict[str, list[tuple[str, str]]] = {}
    for (kind, name), el in sorted(state["elements"].items()):
        if kind == "event" and el.get("state", "draft") == "draft" and name not in have:
            cat, _, ev = name.partition(".")
            cmd = el.get("command") or ev
            if not all(WORD.match(w or "") for w in (cat, ev, cmd)):
                raise ValueError(f"event {name!r} (command {cmd!r}): category, event and command are lowercase words with underscores")
            drafts.setdefault(cat, []).append((cmd, ev))
    lines = real.splitlines()
    inserts: dict[int, list[str]] = {}  # index of the closing-brace line -> lines to put before it
    def block(items, indent):
        out = []
        for cmd, ev in items:
            out += [f"{indent}# rascunho: só no grafo (plano {state['slug']}), ainda não está no código.",
                    f'{indent}"{cmd}": "{ev}",']
        return out
    for cat, items in drafts.items():
        if cat in cats:
            end = cats[cat].end_lineno - 1
            if lines[end].strip() not in ("}", "},"):
                raise ValueError(f"category {cat!r}: its closing brace must be on a line of its own")
            inserts.setdefault(end, []).extend(block(items, "        "))
        else:
            end = node.end_lineno - 1
            if lines[end].strip() != "}":
                raise ValueError("the closing brace of EVENTS must be on a line of its own")
            inserts.setdefault(end, []).extend([f'    "{cat}": {{', *block(items, "        "), "    },"])
    out = []
    for i, line in enumerate(lines):
        out += inserts.get(i, [])
        out.append(line)
    return "\n".join(out) + "\n"


def sync(repo: str | Path, state: dict) -> Path | None:
    """Rewrite the console's SOURCE when the plan names one (plan.started console_source); the file only changes if its text does."""
    cs, ef = state.get("console_source"), state.get("events_file")
    if not cs or not ef:
        return None
    base = Path(repo).expanduser()
    def at(x):
        q = Path(x).expanduser()
        return q if q.is_absolute() else base / q
    text = render_source(at(ef).read_text(encoding="utf-8"), state)
    out = at(cs)
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8")
    return out


def render(slug: str, state: dict, d: dict) -> str:
    lines = [f"plano {slug}  (domínio {state['domain'] or '?'}" + (", confirmado" if state["confirmed"] else ", em rascunho") + ")"]
    if not d["events_read"]:
        lines.append("  sem leitor de EVENTS (plan.started sem events_file): só as telas são conferidas")
    for key, title in (("to_build", "a construir (rascunho, ainda não está no código)"),
                       ("built", "construído (rascunho que o código já tem: use --mark para virar real)"),
                       ("unplanned", "fora do plano (está no código, não está no desenho)"),
                       ("lost", "perdido (marcado real, sumiu do código)")):
        if key == "lost" and not d[key]:
            continue
        lines.append(f"{title}: {len(d[key])}")
        lines += [f"  {i['kind']:<8} {i['name']}" for i in d[key]]
    for doc in d["documents"]:
        lines.append(f"documento {doc['name']}: {len(doc['decisions'])} decisões, {len(doc['sources'])} fontes, {len(doc['questions'])} perguntas")
        lines += [f"  ? {q}" for q in doc["questions"]]
    return "\n".join(lines)


def load(repo: str, slug: str) -> tuple[Path, list[dict], dict]:
    path = plan_path(repo, slug)
    events = read_events(path)
    if not events:
        raise SystemExit(f"no plan at {path}: run plan.sh start {slug} --repo {repo}")
    return path, events, project(events)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plan.sh", description="The plan of a task in Upstream and its drift from the code.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, *, slug=True):
        if slug:
            p.add_argument("slug")
        p.add_argument("--repo", default=".", help="the project's repo (default: here)")
        p.add_argument("--actor", default="agent")
    s = sub.add_parser("start", help="open <repo>/.plan/<slug>.jsonl (plan.started); a plan already open is left as it is")
    common(s)
    s.add_argument("--domain", help="the dev-console domain (default: the slug)")
    s.add_argument("--events-file", help="the Python file whose EVENTS the code records (read with ast)")
    s.add_argument("--console-source", help="the file the dev-console reads as SOURCE: the events file plus the drafts (written by plan.sh)")
    a = sub.add_parser("add", help="draw or change one element (element.updated)")
    common(a)
    a.add_argument("--kind", required=True, choices=KINDS)
    a.add_argument("--name", required=True)
    a.add_argument("--state", choices=STATES)
    a.add_argument("--command", help="event: the command that records it (default: the event's name)")
    a.add_argument("--after", help="event: the event it follows (an edge)")
    a.add_argument("--event", help="screen: the event it sits above")
    a.add_argument("--file", help="screen: HTML in the repo, relative to it")
    a.add_argument("--url")
    a.add_argument("--text", help="document: what it says")
    a.add_argument("--source", action="append", default=[])
    a.add_argument("--question", action="append", default=[])
    a.add_argument("--decision", action="append", default=[], help='"Decidi X porque Y"')
    a.add_argument("--delete", action="store_true")
    w = sub.add_parser("show", help="the plan as the journal folds it")
    common(w)
    w.add_argument("--json", action="store_true")
    r = sub.add_parser("drift", help="the drawing against the code: to build, built, unplanned")
    common(r)
    r.add_argument("--mark", action="store_true", help="append state real for every draft the code already has")
    r.add_argument("--json", action="store_true")
    r.add_argument("--detailed-exitcode", action="store_true", help="exit 2 when there is any drift (to build, unplanned, lost)")
    y = sub.add_parser("sync", help="rewrite the console's SOURCE from the plan (after a hand edit of the JSONL)")
    common(y)
    c = sub.add_parser("confirm", help="the owner approved the plan (plan.confirmed)")
    common(c)
    c.add_argument("--by", default="owner")
    n = ap.parse_args(argv)

    try:
        if n.cmd == "start":
            path = plan_path(n.repo, n.slug)
            if read_events(path):
                print(f"plan already open: {path}")
                return 0
            append(path, "plan.started", {"slug": n.slug, "domain": n.domain or n.slug, "events_file": n.events_file,
                                                "console_source": n.console_source}, n.actor)
            sync(n.repo, project(read_events(path)))
            print(f"plan open: {path}")
        elif n.cmd == "add":
            path, _, _ = load(n.repo, n.slug)
            v = {"kind": n.kind, "name": n.name}
            if n.delete:
                v["change"] = "deleted"
            else:
                v["state"] = n.state or "draft"
                for k, val in (("command", n.command), ("after", n.after), ("event", n.event), ("file", n.file), ("url", n.url),
                               ("text", n.text)):
                    if val:
                        v[k] = val
                for k, val in (("sources", n.source), ("questions", n.question), ("decisions", n.decision)):
                    if val:
                        v[k] = val
                if n.kind == "event" and not re.match(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$", n.name):
                    raise ValueError("an event is named category.event (lowercase, underscores)")
                if n.command and not WORD.match(n.command):
                    raise ValueError("a command is a lowercase word with underscores")
            print(json.dumps(append(path, "element.updated", v, n.actor), ensure_ascii=False))
            sync(n.repo, project(read_events(path)))
        elif n.cmd == "show":
            _, _, st = load(n.repo, n.slug)
            els = [{"kind": k, "name": nm, **{x: y for x, y in e.items() if x not in ("kind", "name")}} for (k, nm), e in st["elements"].items()]
            print(json.dumps({**st, "elements": els}, ensure_ascii=False, indent=2) if n.json else
                  "\n".join([f"{st['slug']} ({st['domain']}) " + ("confirmado" if st["confirmed"] else "rascunho")] +
                            [f"  {e['kind']:<8} {e['state'] if 'state' in e else '':<5} {e['name']}" for e in els]))
        elif n.cmd == "drift":
            path, _, st = load(n.repo, n.slug)
            d = drift(st, n.repo)
            if n.mark:
                for i in d["built"]:
                    append(path, "element.updated", {"kind": i["kind"], "name": i["name"], "state": "real"}, n.actor)
                if d["built"]:
                    st = project(read_events(path))
                    sync(n.repo, st)
                    d = drift(st, n.repo)
            print(json.dumps(d, ensure_ascii=False, indent=2) if n.json else render(n.slug, st, d))
            if n.detailed_exitcode and (d["to_build"] or d["unplanned"] or d["lost"]):
                return 2
        elif n.cmd == "sync":
            _, _, st = load(n.repo, n.slug)
            out = sync(n.repo, st)
            print(f"console source: {out}" if out else "the plan names no console_source")
        elif n.cmd == "confirm":
            path, _, _ = load(n.repo, n.slug)
            print(json.dumps(append(path, "plan.confirmed", {"by": n.by}, n.actor), ensure_ascii=False))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
