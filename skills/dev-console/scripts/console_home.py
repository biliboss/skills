"""The console's home as a Dynamic View: the widgets agents put on it, in real time.

One append-only journal, `${DEV_CONSOLE_HOME_DIR:-~/.local/share/dev-console/home}/events.jsonl` (outside the registry's
folder: a write beside the registry restarts the console). The server is its only writer, through the POST routes;
agents reach the routes only through `devc home`. Events: `home.widget.shown {id, kind, content, title, span, height}`
(a later one with the same id replaces it), `home.widget.removed {id}`, `home.cleared {}`.

Kinds: `html` (inline markup, drawn in a sandboxed frame), `url` (a page in a frame), `widget` (a domain widget's own
route, `/domain/<slug>/w/<tid>/<event>/<name>`, built by devc).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

KINDS = ("html", "url", "widget")


def journal_path() -> Path:
    d = Path(os.environ.get("DEV_CONSOLE_HOME_DIR", "~/.local/share/dev-console/home")).expanduser()
    return d / "events.jsonl"


def _emit(event: str, value: dict, actor: str = "agent") -> dict:
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"id": uuid.uuid4().hex[:12], "event": event, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "actor": actor or "agent", "value": value}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def widgets() -> list[dict]:
    """The widgets on the home now, in the order they were first shown."""
    p = journal_path()
    cur: dict[str, dict] = {}
    if not p.exists():
        return []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        v = e.get("value") or {}
        if e.get("event") == "home.widget.shown" and v.get("id"):
            w = {**v, "at": e.get("at"), "actor": e.get("actor")}
            if v["id"] in cur:
                cur[v["id"]].update(w)
            else:
                cur[v["id"]] = w
        elif e.get("event") == "home.widget.removed":
            cur.pop(v.get("id"), None)
        elif e.get("event") == "home.cleared":
            cur.clear()
    return list(cur.values())


def show(body: dict, actor: str = "agent") -> dict:
    wid, kind, content = str(body.get("id") or "").strip(), body.get("kind"), body.get("content")
    if not wid or kind not in KINDS or not isinstance(content, str) or not content:
        raise ValueError(f"need id, kind ({'|'.join(KINDS)}) and content")
    value = {"id": wid, "kind": kind, "content": content, "title": str(body.get("title") or wid)}
    for k in ("span", "height"):
        if body.get(k):
            value[k] = int(body[k])
    return _emit("home.widget.shown", value, actor)


def remove(wid: str, actor: str = "agent") -> bool:
    if not any(w["id"] == wid for w in widgets()):
        return False
    _emit("home.widget.removed", {"id": wid}, actor)
    return True


def clear(actor: str = "agent") -> None:
    _emit("home.cleared", {}, actor)


def mtime() -> float:
    p = journal_path()
    return p.stat().st_mtime if p.exists() else 0.0


HOME_JS = r"""
(() => {
  const grid = document.getElementById('home-grid'), logo = document.getElementById('home-logo');
  const BASE = '<style>html{color-scheme:dark}body{margin:0;padding:12px;font:13px ui-monospace,monospace;background:#0a0a0a;color:#e5e5e5}</style>';
  const sig = w => JSON.stringify([w.kind, w.content, w.title, w.span, w.height]);
  function card(w) {
    const c = document.createElement('section');
    c.dataset.id = w.id; c.dataset.sig = sig(w);
    c.className = 'flex flex-col min-h-0 rounded-md border border-neutral-200 dark:border-neutral-800 overflow-hidden';
    c.style.gridColumn = 'span ' + Math.max(1, Math.min(3, w.span || 1));
    c.style.height = (w.height || 360) + 'px';
    const h = document.createElement('div');
    h.className = 'h-7 shrink-0 px-3 leading-7 text-neutral-500 border-b border-neutral-200 dark:border-neutral-800 truncate';
    h.textContent = w.title || w.id;
    const f = document.createElement('iframe');
    f.className = 'flex-1 min-h-0 w-full border-0 bg-white dark:bg-neutral-950';
    if (w.kind === 'html') { f.sandbox = 'allow-scripts'; f.srcdoc = BASE + w.content; } else f.src = w.content;
    c.append(h, f);
    return c;
  }
  function draw(list) {
    logo.style.display = list.length ? 'none' : '';
    grid.style.display = list.length ? '' : 'none';
    const keep = new Map([...grid.children].map(el => [el.dataset.id, el]));
    list.forEach((w, i) => {
      let el = keep.get(w.id);
      if (!el || el.dataset.sig !== sig(w)) { const n = card(w); el ? el.replaceWith(n) : grid.append(n); el = n; }
      keep.delete(w.id);
      if (grid.children[i] !== el) grid.insertBefore(el, grid.children[i] || null);
    });
    keep.forEach(el => el.remove());
    window.__home = list.map(w => w.id);
  }
  const es = new EventSource('/api/home/stream');
  es.onmessage = m => draw(JSON.parse(m.data).widgets);
})();
"""
