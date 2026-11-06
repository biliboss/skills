#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""devc: the dev-console's own CLI, one door for agents and people.

Short text for people, JSON with --json for agents. Reads go to the console's HTTP routes
(/api/domains, /domain/<slug>/state.json, /agent/*); the rest delegates to the skill's scripts
(console.sh, agent.sh, window.sh, check.sh), which stay as they are.

Events are what state.json carries: the history of the entity the domain opens (--task <id> picks another one);
there is no whole-journal route yet.

Global flags (anywhere): --port N (default 5057, env DEVC_PORT), --json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(os.environ.get("DEVC_SCRIPTS_DIR") or Path(__file__).resolve().parent)
DEFAULT_PORT = 5057
SCRIPT_TIMEOUT = 60

USAGE = """usage: devc [--port N] [--json] <command>
  domains                          slug, name, origin of every domain
  show <slug> [--task ID]         the domain as text: lanes, stages, events in order, transitions
  events <slug> [--tail] [-n N]    the journal (--tail follows, polling 1 s, Ctrl-C ends)
  focus                            the current focus ('sem foco ainda' when there is none)
  open <slug|url> [--ev E] [--w W] load it in the native window (marked as the agent's)
  shot                             a fresh snapshot of the window: prints the PNG path
  now | history [n]                what the window shows / the last n navigations
  eval '<js>'                      run js in the window and print the value
  start [port] [--owner N]         start another console instance (console.sh start)
  stop <port> [--force]            stop one (5057 needs --force)
  list [port]                      running instances (console.sh list)
  check <url> [--shot f.png ...]   headless check of a page (check.sh)
  board [kanban args...]           the Kanban: passthrough to kanban.sh (devc board list, devc board move ...)
  home list | rm <id> | clear      the home's live widgets (the Dynamic View)
  home show <id> (--html H | --html-file F | --url U | --widget slug/event/name [--task T])
       [--title T] [--span 1-3] [--height PX]   put or replace a widget on the home, live
  install                          symlink devc into ~/.local/bin"""


class DevcError(Exception):
    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- http


def base(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def http_get(port: int, path: str, timeout: float = 10.0) -> tuple[int, object]:
    """(status, parsed json or text). status 0 = nothing answers."""
    req = urllib.request.Request(base(port) + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, f"nothing answers on port {port}"
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def get_ok(port: int, path: str, what: str) -> object:
    status, body = http_get(port, path)
    if status == 200:
        return body
    if status == 0:
        raise DevcError(str(body))
    err = body.get("error") if isinstance(body, dict) else None
    raise DevcError(f"{what}: port {port} answered {status}" + (f" ({err})" if err else ""))


def state_of(port: int, slug: str, task: str = "") -> dict:
    q = f"?task={urllib.parse.quote(task)}" if task else ""
    status, body = http_get(port, f"/domain/{urllib.parse.quote(slug)}/state.json{q}")
    if status == 200 and isinstance(body, dict):
        return body
    if status == 0:
        raise DevcError(str(body))
    if status == 404:
        err = body.get("error") if isinstance(body, dict) else None
        raise DevcError(f"'{slug}' on port {port}: {err or 'no such domain'} (see: devc domains)")
    raise DevcError(f"state of '{slug}': port {port} answered {status}")


# ---------------------------------------------------------------- rendering


def hms(at: str) -> str:
    return at[11:19] if len(at) >= 19 and at[10] == "T" else at


def ev_line(e: dict) -> str:
    who = e.get("actor") or "-"
    sub = e.get("task_id") or e.get("entity_id") or ""
    return f"{hms(e.get('at', ''))}  {e.get('event', '?')}  {who}" + (f"  [{sub[:8]}]" if sub else "")


def lanes_of(model: dict) -> dict[str, list[str]]:
    """entity -> its stages. The lifecycle when the project has one, else the stage order."""
    life = model.get("lifecycle") or {}
    if life:
        return {k: list(v) for k, v in life.items()}
    order = model.get("stage_order") or []
    return {"(stages)": list(order)} if order else {}


def render_show(slug: str, st: dict) -> str:
    model = st.get("model") or {}
    events = st.get("events") or []
    out = [f"{slug}  {st.get('name', '')}".rstrip()]
    entities = st.get("entities") or {}
    lanes = lanes_of(model)
    out.append("")
    out.append("lanes")
    if not lanes and not entities:
        out.append("  (none)")
    for ent, stages in lanes.items():
        out.append(f"  {ent}: " + " → ".join(stages) if stages else f"  {ent}")
    for key, cls in entities.items():
        if key not in lanes:
            out.append(f"  {key} ({cls})")
    labels = model.get("stage_labels") or {}
    order = model.get("stage_order") or []
    if order:
        out.append("")
        out.append("stages")
        out.append("  " + " → ".join(labels.get(s, s) for s in order))
    nxt = model.get("next") or {}
    edge_cmd = model.get("edge_cmd") or {}
    cmds = model.get("commands") or {}
    out.append("")
    out.append("transitions")
    if not nxt:
        out.append("  (none)")
    for src, dsts in nxt.items():
        for dst in dsts:
            cmd = edge_cmd.get(f"{src}>{dst}") or cmds.get(dst)
            out.append(f"  {src} → {dst}" + (f"  ({cmd})" if cmd else ""))
    counts = st.get("journal_types") or {}
    out.append("")
    out.append("events of the open entity" + (f"  ({sum(counts.values())} in the whole journal)" if counts else ""))
    if not events:
        out.append("  (none yet)")
    # a small git-log graph: one commit per event, the lane is the event's entity
    lane_names = list(lanes) or sorted({(e.get("event") or "?").split(".")[0] for e in events})
    for e in events:
        ent = (e.get("event") or "?").split(".")[0]
        col = lane_names.index(ent) if ent in lane_names else 0
        graph = "".join("*" if i == col else "|" for i in range(max(len(lane_names), 1)))
        out.append(f"  {graph} {ev_line(e)}")
    if counts:
        out.append("")
        out.append("journal types")
        for k, v in counts.items():
            out.append(f"  {v:>4}  {k}")
    return "\n".join(out)


def show_json(slug: str, st: dict) -> dict:
    model = st.get("model") or {}
    return {
        "slug": slug,
        "name": st.get("name"),
        "lanes": lanes_of(model),
        "stages": model.get("stage_order") or [],
        "transitions": [
            {"from": s, "to": d, "command": (model.get("edge_cmd") or {}).get(f"{s}>{d}") or (model.get("commands") or {}).get(d)}
            for s, ds in (model.get("next") or {}).items()
            for d in ds
        ],
        "events": st.get("events") or [],
        "journal_types": st.get("journal_types") or {},
    }


# ---------------------------------------------------------------- scripts


def run_script(name: str, args: list[str], passthrough: bool = False) -> subprocess.CompletedProcess:
    path = HERE / name
    if not path.exists():
        raise DevcError(f"{name} not found next to devc ({HERE})")
    try:
        if passthrough:
            return subprocess.run([str(path), *args])  # start runs the server in the foreground outside herdr: no timeout
        return subprocess.run([str(path), *args], capture_output=True, text=True, timeout=SCRIPT_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise DevcError(f"{name} {' '.join(args)[:40]} took over {SCRIPT_TIMEOUT} s")


def script_out(name: str, args: list[str]) -> str:
    p = run_script(name, args)
    if p.returncode != 0:
        raise DevcError((p.stderr or p.stdout).strip() or f"{name} failed ({p.returncode})", p.returncode)
    return p.stdout


def kv_of(text: str) -> dict:
    """agent.sh prints 'key   value' lines; the last block wins."""
    d: dict = {}
    for line in text.splitlines():
        if line.startswith("--"):
            d = {}
            continue
        k, _, v = line.partition(" ")
        if v.strip():
            d[k] = v.strip()
    return d


# ---------------------------------------------------------------- commands


def cmd_domains(a: dict) -> int:
    rows = get_ok(a["port"], "/api/domains", "domains")
    if a["json"]:
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    print(f"{'SLUG':<18} {'ORIGIN':<10} NAME")
    for r in rows:
        print(f"{r.get('slug', ''):<18} {r.get('origin', ''):<10} {r.get('name', '')}")
    return 0


def cmd_show(a: dict) -> int:
    if not a["args"]:
        raise DevcError("usage: devc show <slug> [--json]", 2)
    slug, task = a["args"][0], ""
    if "--task" in a["args"]:
        i = a["args"].index("--task")
        task = a["args"][i + 1] if i + 1 < len(a["args"]) else ""
    st = state_of(a["port"], slug, task)
    print(json.dumps(show_json(slug, st), ensure_ascii=False) if a["json"] else render_show(slug, st))
    return 0


def parse_events_args(args: list[str]) -> tuple[str, bool, int | None, int | None, str]:
    slug, tail, n, max_polls, task = "", False, None, None, ""
    it = iter(args)
    for x in it:
        if x == "--tail":
            tail = True
        elif x == "-n":
            try:
                n = int(next(it))
            except (StopIteration, ValueError):
                raise DevcError("-n needs a number", 2)
        elif x == "--task":
            task = next(it, "")
        elif x == "--max-polls":  # tests only: bounds the follow loop
            max_polls = int(next(it))
        elif x.startswith("-"):
            raise DevcError(f"unknown option {x}", 2)
        else:
            slug = x
    if not slug:
        raise DevcError("usage: devc events <slug> [--task ID] [--tail] [-n N]", 2)
    return slug, tail, n, max_polls, task


def key_of(e: dict) -> str:
    return e.get("id") or json.dumps(e, sort_keys=True)


def cmd_events(a: dict) -> int:
    slug, tail, n, max_polls, task = parse_events_args(a["args"])
    seen: set[str] = set()

    def emit(events: list[dict]) -> None:
        for e in events:
            seen.add(key_of(e))
            print(json.dumps(e, ensure_ascii=False) if a["json"] else ev_line(e), flush=True)

    events = state_of(a["port"], slug, task).get("events") or []
    seen.update(key_of(e) for e in events)  # everything older than the last N counts as seen, so --tail never replays it
    emit(events[-n:] if n else events)
    if not tail:
        return 0
    polls = 0
    try:
        while max_polls is None or polls < max_polls:
            time.sleep(1.0)
            polls += 1
            try:
                events = state_of(a["port"], slug, task).get("events") or []
            except DevcError:
                continue  # the console may be reloading; the next second tries again
            emit([e for e in events if key_of(e) not in seen])
    except KeyboardInterrupt:
        pass
    return 0


def cmd_focus(a: dict) -> int:
    status, body = http_get(a["port"], "/agent/focus")
    if status == 0:
        raise DevcError(str(body))
    if status != 200:
        print(json.dumps({"focus": None}) if a["json"] else "sem foco ainda")
        return 0
    if a["json"]:
        print(json.dumps(body, ensure_ascii=False))
        return 0
    if not isinstance(body, dict) or not any(body.values()):
        print("sem foco ainda")
        return 0
    for k, v in body.items():
        if v not in (None, "", [], {}):
            print(f"{k:<8} {v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)}")
    return 0


def window_url(a: dict, target: str, ev: str | None, w: str | None) -> str:
    if "://" in target:
        url = target
    else:
        url = f"{base(a['port'])}/domain/{urllib.parse.quote(target)}"
    q = {k: v for k, v in (("ev", ev), ("w", w)) if v}
    q["agent"] = "1"  # the mark: this view was opened by an agent, not by a person
    sep = "&" if "?" in url else "?"
    return url + sep + urllib.parse.urlencode(q)


def cmd_open(a: dict) -> int:
    args, ev, w, target = a["args"], None, None, None
    it = iter(args)
    for x in it:
        if x == "--ev":
            ev = next(it, None)
        elif x == "--w":
            w = next(it, None)
        elif x.startswith("-"):
            raise DevcError(f"unknown option {x}", 2)
        else:
            target = x
    if not target:
        raise DevcError("usage: devc open <slug|url> [--ev E] [--w W]", 2)
    url = window_url(a, target, ev, w)
    out = script_out("agent.sh", ["open", url])
    if a["json"]:
        print(json.dumps({"url": url, **kv_of(out)}, ensure_ascii=False))
    else:
        print(f"opened {url}\n{out.rstrip()}")
    return 0


def cmd_shot(a: dict) -> int:
    out = script_out("agent.sh", ["shot"])
    kv = kv_of(out)
    path = kv.get("shot")
    if not path or path == "-":
        raise DevcError("the window recorded no PNG")
    print(json.dumps(kv, ensure_ascii=False) if a["json"] else path)
    return 0


def cmd_now(a: dict) -> int:
    status, body = http_get(a["port"], "/agent/now")
    return print_lines(a, status, body, many=False)


def cmd_history(a: dict) -> int:
    n = a["args"][0] if a["args"] else "5"
    if not n.isdigit() or not 1 <= int(n) <= 20:
        raise DevcError("history needs a number from 1 to 20", 2)
    status, body = http_get(a["port"], f"/agent/history?n={n}")
    return print_lines(a, status, body, many=True)


def line_text(d: dict) -> str:
    errs = d.get("errors") or []
    return "\n".join(
        [
            f"at      {d.get('at')}",
            f"url     {d.get('url') or '-'}",
            f"domain  {d.get('domain') or '-'}",
            f"module  {d.get('module') or '-'}",
            f"event   {d.get('event') or '-'}",
            f"widget  {d.get('widget') or '-'}",
            f"errors  {len(errs)}" + (f"  first: {errs[0][:160]}" if errs else ""),
            f"shot    {d.get('shot') or '-'}",
        ]
    )


def print_lines(a: dict, status: int, body: object, many: bool) -> int:
    if status == 0:
        raise DevcError(str(body))
    if status != 200:
        err = body.get("error") if isinstance(body, dict) else body
        raise DevcError(f"{err} (port {a['port']} answered {status})")
    rows: list = [body]
    if isinstance(body, list):
        rows = body
    elif isinstance(body, dict) and many:
        rows = body.get("lines") or body.get("history") or [body]
    if a["json"]:
        print(json.dumps(rows if many else rows[0], ensure_ascii=False))
    else:
        print("\n--\n".join(line_text(r) for r in rows))
    return 0


def cmd_eval(a: dict) -> int:
    if not a["args"]:
        raise DevcError("usage: devc eval '<js>'", 2)
    out = script_out("agent.sh", ["eval", a["args"][0]]).rstrip("\n")
    print(json.dumps({"value": out}, ensure_ascii=False) if a["json"] else out)
    return 0


def cmd_start(a: dict) -> int:
    args = list(a["args"])
    if "--owner" not in args:
        args += ["--owner", os.environ.get("DEVC_OWNER") or os.environ.get("USER") or "agent"]
    return run_script("console.sh", ["start", *args], passthrough=True).returncode


def cmd_stop(a: dict) -> int:
    if not a["args"]:
        raise DevcError("usage: devc stop <port> [--force]", 2)
    return run_script("console.sh", ["stop", *a["args"]], passthrough=True).returncode


def cmd_list(a: dict) -> int:
    out = script_out("console.sh", ["list"])
    if a["args"]:
        want = f":{a['args'][0].lstrip(':')}"
        blocks, cur = [], []
        for line in out.splitlines():
            if line.startswith(":") and cur:
                blocks.append(cur)
                cur = []
            cur.append(line)
        blocks.append(cur)
        out = "\n".join("\n".join(b) for b in blocks if b and b[0].strip() == want) or f"no dev-console instance on {want}"
    print(out.rstrip())
    return 0


def cmd_check(a: dict) -> int:
    if not a["args"]:
        raise DevcError("usage: devc check <url> [--shot f.png] [--eval '<js>'] ...", 2)
    return run_script("check.sh", a["args"], passthrough=True).returncode


def cmd_install(a: dict) -> int:
    bin_dir = Path(os.environ.get("DEVC_BIN_DIR") or Path.home() / ".local" / "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    src, dst = HERE / "devc", bin_dir / "devc"
    if dst.is_symlink() or dst.exists():
        if dst.is_symlink() and dst.resolve() == src.resolve():
            print(f"already: {dst} -> {src}")
            return 0
        raise DevcError(f"{dst} exists and is not this devc; remove it first")
    dst.symlink_to(src)
    print(f"{dst} -> {src}" + ("" if str(bin_dir) in os.environ.get("PATH", "").split(":") else f"\n(add {bin_dir} to PATH)"))
    return 0


# ---------------------------------------------------------------- kanban


def kanban_path() -> Path:
    env = os.environ.get("DEVC_KANBAN_SH")
    return Path(env) if env else Path(__file__).resolve().parent.parent.parent / "kanban" / "scripts" / "kanban.sh"


def run_kanban(args: list[str], passthrough: bool = False) -> subprocess.CompletedProcess:
    path = kanban_path()
    if not path.exists():
        raise DevcError(f"kanban.sh not found ({path}); set DEVC_KANBAN_SH")
    try:
        if passthrough:
            return subprocess.run([str(path), *args])
        return subprocess.run([str(path), *args], capture_output=True, text=True, timeout=SCRIPT_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise DevcError(f"kanban.sh {' '.join(args)[:40]} took over {SCRIPT_TIMEOUT} s")


def cmd_board(a: dict) -> int:
    # --json is global in devc but kanban's list/show/money take it too: hand it back
    args = list(a["args"])
    if a["json"] and args[:1] in (["list"], ["show"], ["money"]) and "--json" not in args:
        args.append("--json")
    return run_kanban(args, passthrough=True).returncode


def cmd_browse(a: dict) -> int:
    """devc browse <url>: the page an agent runs (a landing, a dev server) inside the console's Browser module."""
    target = next((x for x in a["args"] if not x.startswith("-")), None)
    if not target:
        raise DevcError("usage: devc browse <url>", 2)
    if "://" not in target:
        target = "http://" + target
    return cmd_open({**a, "args": [f"http://127.0.0.1:{a['port']}/browser?url={urllib.parse.quote(target, safe='')}"]})


def http_post(port: int, path: str, body: dict) -> tuple[int, object]:
    req = urllib.request.Request(base(port) + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Devc-Actor": os.environ.get("DEVC_ACTOR", "agent")})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            status, raw = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, f"nothing answers on port {port}"
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def cmd_home(a: dict) -> int:
    """devc home list | show | rm | clear: the home's live widgets (the Dynamic View). The server writes the journal."""
    args = list(a["args"])
    sub = args.pop(0) if args else "list"
    opts, pos, i = {}, [], 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            opts[args[i][2:]] = args[i + 1]; i += 2
        else:
            pos.append(args[i]); i += 1
    port = a["port"]
    if sub == "list":
        status, body = http_get(port, "/api/home")
        if status != 200:
            raise DevcError(f"/api/home answered {status}: {body}")
        if a["json"]:
            print(json.dumps(body, ensure_ascii=False, indent=2))
        else:
            for w in body["widgets"]:
                print(f"{w['id']}\t{w['kind']}\t{w.get('title', '')}\t{w.get('actor', '')}")
            if not body["widgets"]:
                print("home vazia (só o logo)")
        return 0
    if sub == "show":
        if not pos:
            raise DevcError("usage: devc home show <id> --html H | --html-file F | --url U | --widget slug/event/name", 2)
        if "html-file" in opts:
            kind, content = "html", Path(opts["html-file"]).expanduser().read_text(encoding="utf-8")
        elif "html" in opts:
            kind, content = "html", opts["html"]
        elif "url" in opts:
            kind, content = "url", opts["url"] if "://" in opts["url"] or opts["url"].startswith("/") else "http://" + opts["url"]
        elif "widget" in opts:
            parts = opts["widget"].split("/")
            if len(parts) != 3:
                raise DevcError("--widget needs slug/event/name", 2)
            slug, event, name = (urllib.parse.quote(x, safe="") for x in parts)
            task = opts.get("task", "")
            kind, content = "widget", f"/domain/{slug}/w/{urllib.parse.quote(task or '_', safe='')}/{event}/{name}" + (f"?task={urllib.parse.quote(task)}" if task else "")
        else:
            raise DevcError("show needs --html, --html-file, --url or --widget", 2)
        body = {"id": pos[0], "kind": kind, "content": content, "title": opts.get("title", pos[0])}
        for k in ("span", "height"):
            if k in opts:
                body[k] = int(opts[k])
        status, out = http_post(port, "/api/home/show", body)
    elif sub == "rm":
        if not pos:
            raise DevcError("usage: devc home rm <id>", 2)
        status, out = http_post(port, "/api/home/rm", {"id": pos[0]})
    elif sub == "clear":
        status, out = http_post(port, "/api/home/clear", {})
    else:
        raise DevcError("usage: devc home list | show | rm | clear", 2)
    if status != 200:
        raise DevcError(f"{sub} answered {status}: {out}")
    print(json.dumps(out, ensure_ascii=False) if a["json"] else f"ok: home {sub} {pos[0] if pos else ''}".rstrip())
    return 0


COMMANDS = {
    "browse": cmd_browse,
    "domains": cmd_domains, "show": cmd_show, "events": cmd_events, "focus": cmd_focus, "open": cmd_open,
    "shot": cmd_shot, "now": cmd_now, "history": cmd_history, "eval": cmd_eval, "start": cmd_start,
    "stop": cmd_stop, "list": cmd_list, "check": cmd_check, "install": cmd_install,
    "board": cmd_board, "home": cmd_home,
}


def parse(argv: list[str]) -> dict:
    """--port and --json are global: they may sit anywhere before a `--`-less rest."""
    port = int(os.environ.get("DEVC_PORT") or DEFAULT_PORT)
    as_json, rest, i = False, [], 0
    while i < len(argv):
        x = argv[i]
        if x == "--json":
            as_json = True
        elif x == "--port" and i + 1 < len(argv):
            i += 1
            if not argv[i].isdigit():
                raise DevcError("--port needs a number", 2)
            port = int(argv[i])
        elif x.startswith("--port="):
            v = x.split("=", 1)[1]
            if not v.isdigit():
                raise DevcError("--port needs a number", 2)
            port = int(v)
        else:
            rest.append(x)
        i += 1
    if not rest or rest[0] in ("-h", "--help", "help"):
        return {"cmd": None, "args": [], "port": port, "json": as_json}
    return {"cmd": rest[0], "args": rest[1:], "port": port, "json": as_json}


def main(argv: list[str]) -> int:
    try:
        a = parse(argv)
        if a["cmd"] is None:
            print(USAGE)
            return 0
        fn = COMMANDS.get(a["cmd"])
        if not fn:
            raise DevcError(f"unknown command '{a['cmd']}'\n{USAGE}", 2)
        return fn(a)
    except DevcError as e:
        print(f"devc: {e}", file=sys.stderr)
        return e.code
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
