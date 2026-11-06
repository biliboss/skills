#!/usr/bin/env python3
"""view.py (skill thread) — the thread agent's ONLY output: the thread's screen (view.json).
The human never reads the agent's chat text; they read this screen.

  view.py <sid> get                      print the current view (JSON)
  view.py <sid> goal "<title>" ["<subtitle>"]
  view.py <sid> steps '<json list of {"text","state":"done|doing|blocked|todo","note"}>'
  view.py <sid> step <n> <state> ["<note>"]          (n starts at 1)
  view.py <sid> artifacts '<json list of {"key","name","state":"empty|ready","path"}>'
  view.py <sid> decision "<text>" [--cmd "<command>"] [--option "<label>" <pct>]...
        each option carries your confidence %, all options summing 100. Label "<artifact key> · <name>";
        view.py renumbers by rank: 01 is always the most recommended, artifacts follow the same numbers
  view.py <sid> decision --clear
  view.py <sid> pulse "<one line of life>"
  view.py <sid> worker add <id> "<what it does>" [--pid PID]   register background work (Agentes queue)
  view.py <sid> worker done <id> ["<result>"]  |  worker fail <id> "<why>"

Artifacts with a "path" get an HTML gallery automatically; its URL shows on the screen.
  view.py <sid> put  < full.json         replace the whole view

Rules: short, for a human. One goal. 3-6 steps. A decision only when the owner must act.
"""
import json, os, sys, tempfile, time

ROOT = os.path.expanduser(os.environ.get("THREADVIEW_DIR", "~/.local/state/threadview"))
STATES = {"done", "doing", "blocked", "todo"}

def path(sid): return os.path.join(ROOT, f"{sid}.json")

def load(sid):
    try:
        with open(path(sid)) as f: return json.load(f)
    except FileNotFoundError:
        return {"goal": {"title": "", "subtitle": ""}, "steps": [], "artifacts": [], "decision": None, "pulse": ""}

def save(sid, v):
    os.makedirs(ROOT, exist_ok=True)
    v["updated_at"] = time.time()
    fd, tmp = tempfile.mkstemp(dir=ROOT, suffix=".tmp")
    with os.fdopen(fd, "w") as f: json.dump(v, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path(sid))  # atomic: the TUI never reads half a file

def gallery(sid, v):
    """Full-screen grid of the artifacts in the dev-console look; opened in the DevConsole window.
    Each image is isolated (<img src=data:>), so SVG ids never collide. Confidence comes from the decision."""
    arts = [a for a in v.get("artifacts", []) if a.get("path")]
    if not arts: v.pop("url", None); return
    import html, base64, mimetypes
    pct = {}
    for o in (v.get("decision") or {}).get("options", []):
        if isinstance(o, dict): pct[o["label"].split("·")[0].strip()] = o["pct"]
    if pct: arts = [a for a in arts if a.get("key", "") in pct]  # only what is being decided  # the grid shows the options being decided
    arts.sort(key=lambda a: a.get("key", ""))  # A B C D; the recommended is marked, not moved
    for a in arts:
        if "pct" in a: pct.setdefault(a.get("key", ""), a["pct"])  # a tournament puts the % on the artifact
    top = max(pct.values()) if pct else None
    cells = []
    for a in arts:
        p = os.path.expanduser(a["path"])
        if os.path.exists(p):
            mt = "image/svg+xml" if p.endswith(".svg") else (mimetypes.guess_type(p)[0] or "image/png")
            src = f"data:{mt};base64,{base64.b64encode(open(p, 'rb').read()).decode()}"
            img = f'<img class=big src="{src}"><div class=sizes><img src="{src}" style="width:16px;height:16px"><img src="{src}" style="width:32px;height:32px"><span>16 · 32 px</span></div>'
        else: img = '<div class=miss>sem arquivo</div>'
        k = a.get("key", ""); n = a.get("name", "").split(":")[0].split("(")[0].strip()
        pc = pct.get(k); rec = pc is not None and pc == top
        bar = f'<div class=bar><i style="width:{pc}%"></i></div><b class=pct>{pc}%</b>' if pc is not None else ""
        cells.append(f'<section class="{"rec" if rec else ""}"><div class=stage>{img}</div>'
                     f'<footer><span class=k>{html.escape(k)}</span><span class=n>{html.escape(n)}</span>'
                     f'{"<span class=tag>recomendado</span>" if rec else ""}{bar}</footer></section>')
    g = v.get("goal") or {}
    cols = 2 if len(cells) <= 4 else 3
    doc = f"""<!doctype html><meta charset=utf-8><title>{html.escape(g.get("title","thread"))}</title>
<style>
*{{box-sizing:border-box;margin:0}}
html,body{{height:100%;background:#0a0a0a;color:#e8e8e8;font:14px ui-monospace,"SF Mono",Menlo,monospace;overflow:hidden}}
body{{display:grid;grid-template-rows:auto 1fr}}
header{{padding:18px 28px;display:flex;gap:14px;align-items:baseline;border-bottom:1px solid #1c1c1c}}
header h1{{font-size:15px;font-weight:600;color:#fff}} header p{{color:#777;font-size:13px}}
main{{display:grid;grid-template-columns:repeat({cols},minmax(0,1fr));grid-auto-rows:1fr;gap:1px;background:#1c1c1c;min-height:0}}
section{{background:#0a0a0a;display:grid;grid-template-rows:1fr auto;min-height:0}}
section.rec{{background:#0d120e}}
.stage{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px;min-height:0}}
img{{filter:invert(1)}} img.big{{height:min(26vh,26vw);max-width:80%;object-fit:contain}}
.sizes{{display:flex;gap:16px;align-items:center;color:#555;font-size:12px}}
footer{{display:flex;gap:12px;align-items:center;padding:14px 22px;border-top:1px solid #161616}}
.k{{color:#fff;font-weight:700}} .n{{color:#999}}
.tag{{color:#4ade80;font-size:12px}} .rec .n{{color:#ddd}}
.bar{{margin-left:auto;width:120px;height:4px;background:#222;border-radius:2px;overflow:hidden}}
.bar i{{display:block;height:100%;background:#555}} .rec .bar i{{background:#4ade80}}
.pct{{width:44px;text-align:right;color:#777}} .rec .pct{{color:#4ade80}}
.miss{{color:#555}}
</style>
<header><h1>{html.escape(g.get("title",""))}</h1><p>{html.escape(g.get("subtitle",""))}</p></header>
<main>{"".join(cells)}</main>"""
    out = os.path.join(ROOT, f"{sid}.html")
    with open(out, "w") as f: f.write(doc)
    v["url"] = "file://" + out

def rank(v):
    """Number = rank: options sorted by confidence become 01, 02…; artifacts with the same old key follow."""
    d = v.get("decision") or {}
    opts = [o for o in d.get("options", []) if isinstance(o, dict)]
    if not opts: return
    opts.sort(key=lambda o: -o["pct"])
    remap = {}
    for r, o in enumerate(opts, 1):
        old, _, nm = o["label"].partition("·")
        new = f"{r:02d}"
        if nm: remap[old.strip()] = new; o["label"] = f"{new} · {nm.strip()}"
    d["options"] = opts
    arts = v.get("artifacts", [])
    for a in arts: a["key"] = remap.get(a.get("key", ""), a.get("key", ""))
    arts.sort(key=lambda a: a.get("key", ""))

def die(msg): print(f"view.py: {msg}", file=sys.stderr); sys.exit(2)

def main(a):
    if len(a) < 2 or a[1] in ("help", "-h", "--help"): print(__doc__); return
    sid, cmd, rest = a[0], a[1], a[2:]
    v = load(sid)
    if cmd == "get": print(json.dumps(v, ensure_ascii=False, indent=1)); return
    if cmd == "goal":
        if not rest: die("goal needs a title")
        v["goal"] = {"title": rest[0], "subtitle": rest[1] if len(rest) > 1 else ""}
    elif cmd == "steps":
        steps = json.loads(rest[0])
        for s in steps:
            if s.get("state", "todo") not in STATES: die(f"bad state {s.get('state')}; use {sorted(STATES)}")
        v["steps"] = steps
    elif cmd == "step":
        n, st = int(rest[0]), rest[1]
        if st not in STATES: die(f"bad state {st}; use {sorted(STATES)}")
        if not 1 <= n <= len(v["steps"]): die(f"no step {n}; there are {len(v['steps'])}")
        v["steps"][n - 1]["state"] = st
        if len(rest) > 2: v["steps"][n - 1]["note"] = rest[2]
    elif cmd == "artifacts":
        v["artifacts"] = json.loads(rest[0])
    elif cmd == "decision":
        if rest[:1] == ["--clear"]: v["decision"] = None
        else:
            if not rest: die("decision needs a text")
            d, i = {"text": rest[0], "cmd": None, "options": []}, 1
            while i < len(rest):
                if rest[i] == "--cmd": d["cmd"] = rest[i + 1]; i += 2
                elif rest[i] == "--option":
                    if i + 2 >= len(rest) or not rest[i + 2].rstrip("%").isdigit(): die(f"--option {rest[i + 1]!r} needs a confidence %: --option \"<label>\" 60")
                    d["options"].append({"label": rest[i + 1], "pct": int(rest[i + 2].rstrip("%"))}); i += 3
                else: die(f"unknown {rest[i]}")
            if d["options"]:
                tot = sum(o["pct"] for o in d["options"])
                if tot != 100: die(f"confidence must sum 100 across options (got {tot})")
                d["options"].sort(key=lambda o: -o["pct"])  # the first is always the recommended
            v["decision"] = d
    elif cmd == "worker":
        sub, wid = rest[0], rest[1]
        ws = v.setdefault("workers", [])
        w = next((x for x in ws if x["id"] == wid), None)
        if sub == "add":
            if w: die(f"worker {wid} exists")
            w = {"id": wid, "what": rest[2] if len(rest) > 2 else wid, "state": "running", "started_at": time.time()}
            if "--pid" in rest: w["pid"] = int(rest[rest.index("--pid") + 1])
            ws.append(w)
        elif sub in ("done", "fail"):
            if not w: die(f"no worker {wid}")
            w.update(state=sub, ended_at=time.time(), note=rest[2] if len(rest) > 2 else "")
        else: die("worker add|done|fail")
    elif cmd == "pulse":
        v["pulse"] = rest[0] if rest else ""
    elif cmd == "put":
        v = json.load(sys.stdin)
    else: die(f"unknown command {cmd}; run: view.py {sid} help")
    if cmd in ("artifacts", "put", "decision"): rank(v); gallery(sid, v)
    save(sid, v)
    print("ok" + (f" · galeria: {v['url']}" if cmd in ("artifacts", "put") and v.get("url") else ""))

if __name__ == "__main__": main(sys.argv[1:])
