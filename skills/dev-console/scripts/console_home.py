"""The console's home as a Dynamic View: the widgets agents (and the owner) put on it, in real time.

The source of truth is SQLite, table `home` of `${DEV_CONSOLE_DB}` (see console_store.py): one row per placement,
starting with only the logo widget. The server is the only writer from code, through the POST routes that agents reach
only with `devc home`; the owner may edit rows in a SQLite app and the page follows (SSE, watchfiles on the db).

The old append-only journal `${DEV_CONSOLE_HOME_DIR:-~/.local/share/dev-console/home}/events.jsonl` is archive only: it is
read once, when the `home` table is first created, to migrate its placements, and never written or deleted again.
Old events: `home.widget.shown {id, kind, content, title, span, height}`, `home.widget.removed {id}`, `home.cleared {}`.

Sources: `widget` (a registered widget, `widgets.id` = `<domain>/<event>/<Name>`, plus the `task` it renders), `html`
(inline markup, a sandboxed frame), `url` (a page in a frame).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import console_store as ST

KINDS = ST.SOURCES


def journal_path() -> Path:
    d = Path(os.environ.get("DEV_CONSOLE_HOME_DIR", "~/.local/share/dev-console/home")).expanduser()
    return d / "events.jsonl"


def legacy_widgets() -> list[dict]:
    """The placements the old journal ends with, in the order they were first shown (read only)."""
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


def init() -> None:
    ST.init(legacy_widgets())


def widgets() -> list[dict]:
    return ST.list_home()


def show(body: dict, actor: str = "agent") -> dict:
    return ST.show(body, actor)


def remove(wid: str, actor: str = "agent") -> bool:
    return ST.remove(wid)


def clear(actor: str = "agent") -> None:
    ST.clear(actor)


HOME_JS = r"""
(() => {
  const grid = document.getElementById('home-grid');
  const BASE = '<style>html{color-scheme:dark}body{margin:0;padding:12px;font:13px ui-monospace,monospace;background:#0a0a0a;color:#e5e5e5}</style>';
  const sig = w => JSON.stringify([w.source, w.widget_id, w.content, w.task, w.title, w.span, w.height, w.src, w.chrome]);
  const BORDER = 'border border-neutral-200 dark:border-neutral-800';
  function inject(el, html) {  // a fragment's <script> tags do not run through innerHTML: re-create them
    el.innerHTML = html;
    el.querySelectorAll('script').forEach(o => { const n = document.createElement('script'); n.textContent = o.textContent; o.replaceWith(n); });
  }
  function frame(w) {
    const f = document.createElement('iframe');
    f.className = 'flex-1 min-h-0 w-full border-0 bg-white dark:bg-neutral-950';
    if (w.source === 'html') { f.sandbox = 'allow-scripts'; f.srcdoc = BASE + w.content; }
    else f.src = w.src || w.content;
    return f;
  }
  function card(w, kids) {
    const c = document.createElement('section');
    c.dataset.id = w.id; c.dataset.sig = sig(w) + kids.map(k => k.id).join();
    c.className = 'flex flex-col min-h-0 overflow-hidden ' + (w.chrome ? 'rounded-md ' + BORDER : '');
    c.style.gridColumn = 'span ' + w.span;
    if (w.height || !kids.length) c.style.height = (w.height || 360) + 'px';
    if (w.chrome) {
      const h = document.createElement('div');
      h.className = 'h-7 shrink-0 px-3 leading-7 text-neutral-500 border-b border-neutral-200 dark:border-neutral-800 truncate';
      h.textContent = w.title || w.id;
      c.append(h);
    }
    if (!w.chrome) {  // the logo: the widget's own markup, drawn in place
      const b = document.createElement('div');
      b.className = 'flex-1 min-h-0 flex items-center justify-center text-neutral-800 dark:text-neutral-200';
      fetch(w.src, {headers: {'HX-Request': 'true'}}).then(r => r.text()).then(t => inject(b, t));
      c.append(b);
    } else if (w.src || w.content) c.append(frame(w));
    if (kids.length) {  // composition: the placements inside this one
      const inner = document.createElement('div');
      inner.className = 'flex-1 min-h-0 overflow-auto grid gap-3 p-3';
      inner.style.cssText = 'grid-template-columns:repeat(auto-fill,minmax(280px,1fr));align-content:start';
      kids.forEach(k => inner.append(k.el));
      c.append(inner);
    }
    return c;
  }
  function build(list) {  // top-level first, each with its children (already ordered by position)
    const kids = new Map();
    list.forEach(w => { const p = w.parent_id || ''; (kids.get(p) || kids.set(p, []).get(p)).push(w); });
    const make = w => { const k = (kids.get(w.id) || []).map(x => ({id: x.id, el: make(x)})); return card(w, k); };
    return (kids.get('') || []).map(w => ({id: w.id, sig: sig(w) + JSON.stringify((kids.get(w.id) || []).map(x => sig(x))), w, make: () => make(w)}));
  }
  function draw(list) {
    const solo = list.length === 1 && !list[0].chrome;  // only the logo: centred in the empty canvas
    grid.style.display = list.length ? (solo ? 'flex' : 'grid') : 'none';
    grid.style.alignItems = solo ? 'center' : ''; grid.style.justifyContent = solo ? 'center' : '';
    const keep = new Map([...grid.children].map(el => [el.dataset.id, el]));
    build(list).forEach((t, i) => {
      let el = keep.get(t.w.id);
      if (!el || el.dataset.tree !== t.sig) { const n = t.make(); n.dataset.tree = t.sig; el ? el.replaceWith(n) : grid.append(n); el = n; }
      keep.delete(t.w.id);
      if (grid.children[i] !== el) grid.insertBefore(el, grid.children[i] || null);
      if (solo) { el.style.height = '160px'; el.style.width = '160px'; } else el.style.width = '';
    });
    keep.forEach(el => el.remove());
    window.__home = list.map(w => w.id);
  }
  const es = new EventSource('/api/home/stream');
  es.onmessage = m => draw(JSON.parse(m.data).widgets);
})();
"""
