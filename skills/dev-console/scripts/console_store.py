"""The console's one SQLite file: `widgets` (the catalogue of every domain widget) and `home` (what is on the Home).

`${DEV_CONSOLE_DB:-~/.local/share/dev-console/dev-console.sqlite}`, WAL mode. Keep it OUTSIDE the folders the reloader
watches (the registry's folder restarts the console on any write).

- `widgets`: one row per widget of every loaded project, identity `<domain>/<event>/<Name>` (the URL of the widget,
  `devc home --widget`). The code files stay the source of the code; the console rewrites the table from the loaded
  projects at start and on every hot reload (a reload is a new process), only when something changed.
- `home`: one row per placement on the Home, in `position` order; `parent_id` composes (a placement inside another).
  Seeded with exactly one row, the logo widget. The server is the only writer from code (routes -> `show/remove/clear`);
  the owner may edit rows in any SQLite app, and `changes()` notices it (watchfiles on the db and its -wal file).
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import re
import sqlite3
import time
from pathlib import Path

LOGO_ID = "dev-console/domain.updated/Logo"  # the logo is a real widget of the dev-console's own project
SOURCES = ("widget", "html", "url")
SAFE_URL = re.compile(r"^(https?://|/(?!/))", re.I)  # never javascript:, data: or a protocol-relative URL in a frame

SCHEMA = """
CREATE TABLE IF NOT EXISTS widgets (
  id TEXT PRIMARY KEY,           -- identidade: <domínio>/<evento>/<Nome>, a mesma da URL /w/<entidade>/<evento>/<Nome>
  domain TEXT NOT NULL, event TEXT NOT NULL, name TEXT NOT NULL,
  kind TEXT NOT NULL,            -- widget | expected
  position INTEGER, function TEXT, module TEXT, file TEXT, line INTEGER,
  fake INTEGER NOT NULL DEFAULT 0, roles TEXT,  -- roles: JSON (home, module:X, entity_part:Y)
  code TEXT, code_sha256 TEXT, project TEXT, exported_at TEXT NOT NULL);
"""
HOME_SCHEMA = """
CREATE TABLE home (
  id TEXT PRIMARY KEY,           -- placement id: what `devc home show <id>` uses
  widget_id TEXT,                -- widgets.id when source = widget; null for raw html/url
  source TEXT NOT NULL CHECK (source IN ('widget','html','url')),
  content TEXT,                  -- the html or the url
  task TEXT,                     -- the entity a widget renders (optional)
  title TEXT,
  position INTEGER NOT NULL,     -- order on the grid
  span INTEGER NOT NULL DEFAULT 1,
  height INTEGER,
  parent_id TEXT,                -- composition: a placement inside another
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, actor TEXT);
"""
COLS = ("id", "widget_id", "source", "content", "task", "title", "position", "span", "height", "parent_id",
        "created_at", "updated_at", "actor")


def db_path() -> Path:
    return Path(os.environ.get("DEV_CONSOLE_DB", "~/.local/share/dev-console/dev-console.sqlite")).expanduser()


def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# --- home ------------------------------------------------------------------------------------------------------
def init(legacy: list[dict] | None = None) -> None:
    """Create the tables. The first time `home` exists it gets the logo row, then the placements of the old JSONL
    journal (`legacy`, read by console_home; the file itself is never touched)."""
    db = connect()
    try:
        db.executescript(SCHEMA)
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='home'").fetchone():
            db.executescript(HOME_SCHEMA)
            t = now()
            db.execute("INSERT INTO home (id, widget_id, source, title, position, span, height, created_at, updated_at, actor)"
                       " VALUES ('logo', ?, 'widget', 'dev-console', 0, 1, 160, ?, ?, 'system')", (LOGO_ID, t, t))
            db.commit()
            for w in legacy or []:
                _upsert(db, _from_legacy(w), w.get("actor") or "agent", w.get("at"))
        db.commit()
    finally:
        db.close()


def _from_legacy(w: dict) -> dict:
    body = {k: w[k] for k in ("id", "title", "span", "height") if w.get(k)}
    if w.get("kind") == "widget":  # /domain/<slug>/w/<task|_>/<event>/<Name>[?task=]
        path, _, query = str(w.get("content", "")).partition("?")
        parts = path.strip("/").split("/")
        if len(parts) == 6 and parts[0] == "domain" and parts[2] == "w":
            from urllib.parse import unquote
            task = unquote(query[5:]) if query.startswith("task=") else None
            return {**body, "source": "widget", "widget_id": "/".join(unquote(x) for x in (parts[1], parts[4], parts[5])),
                    "task": task}
        return {**body, "source": "url", "content": w.get("content")}
    return {**body, "source": w.get("kind"), "content": w.get("content")}


def _upsert(db: sqlite3.Connection, body: dict, actor: str, at: str | None = None) -> dict:
    wid = str(body.get("id") or "").strip()
    source = body.get("source") or body.get("kind")
    content, widget_id = body.get("content"), body.get("widget_id")
    if source == "widget" and not widget_id and isinstance(content, str):  # an older devc sent the widget's route
        old = _from_legacy({"id": wid, "kind": "widget", "content": content})
        source, widget_id, content = old["source"], old.get("widget_id"), old.get("content")
        body = {**body, "task": body.get("task") or old.get("task")}
    if not wid or source not in SOURCES:
        raise ValueError(f"need id and source ({'|'.join(SOURCES)})")
    if source == "widget" and not widget_id:
        raise ValueError("source widget needs widget_id (<domain>/<event>/<Name>)")
    if source != "widget" and not (isinstance(content, str) and content):
        raise ValueError(f"source {source} needs content")
    if source == "url" and not SAFE_URL.match(content):
        raise ValueError("url must be http(s):// or a path starting with /")
    parent = body.get("parent_id") or None
    if parent == wid:
        raise ValueError("parent_id cannot be the placement itself")
    t = at or now()
    old = db.execute("SELECT * FROM home WHERE id=?", (wid,)).fetchone()
    if body.get("position") is not None:
        pos = int(body["position"])
    elif old:
        pos = old["position"]
    else:
        pos = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM home").fetchone()[0]
    span, height = body.get("span") or (old["span"] if old else 1), body.get("height") or (old["height"] if old else None)
    db.execute(
        "INSERT INTO home (id, widget_id, source, content, task, title, position, span, height, parent_id, created_at, updated_at, actor)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET widget_id=excluded.widget_id, source=excluded.source,"
        " content=excluded.content, task=excluded.task, title=excluded.title, position=excluded.position, span=excluded.span,"
        " height=excluded.height, parent_id=excluded.parent_id, updated_at=excluded.updated_at, actor=excluded.actor",
        (wid, widget_id if source == "widget" else None, source, content if source != "widget" else None, body.get("task") or None,
         str(body.get("title") or wid), pos, int(span), int(height) if height else None, parent, old["created_at"] if old else t, t, actor))
    db.commit()
    return dict(db.execute("SELECT * FROM home WHERE id=?", (wid,)).fetchone())


def show(body: dict, actor: str = "agent") -> dict:
    db = connect()
    try:
        return _upsert(db, body, actor or "agent")
    finally:
        db.close()


def remove(wid: str) -> bool:
    """Delete a placement and, composed inside it, everything below."""
    db = connect()
    try:
        gone, todo = set(), [wid]
        while todo:
            cur = todo.pop()
            if cur in gone:
                continue
            gone.add(cur)
            todo += [r[0] for r in db.execute("SELECT id FROM home WHERE parent_id=?", (cur,))]
        n = 0
        for g in gone:
            n += db.execute("DELETE FROM home WHERE id=?", (g,)).rowcount
        db.commit()
        return n > 0
    finally:
        db.close()


def clear(actor: str = "agent") -> None:
    """Back to the initial state: only the logo."""
    db = connect()
    try:
        t = now()
        db.execute("DELETE FROM home")
        db.execute("INSERT INTO home (id, widget_id, source, title, position, span, height, created_at, updated_at, actor)"
                   " VALUES ('logo', ?, 'widget', 'dev-console', 0, 1, 160, ?, ?, ?)", (LOGO_ID, t, t, actor or "system"))
        db.commit()
    finally:
        db.close()


def src_of(row: dict) -> str | None:
    """The route a widget placement draws: /domain/<slug>/w/<task|_>/<event>/<Name>."""
    parts = str(row.get("widget_id") or "").split("/")
    if row.get("source") != "widget" or len(parts) != 3:
        return None
    from urllib.parse import quote
    task = row.get("task") or ""
    return f"/domain/{quote(parts[0], safe='')}/w/{quote(task or '_', safe='')}/{quote(parts[1], safe='')}/{quote(parts[2], safe='')}" + (
        f"?task={quote(task)}" if task else "")


def list_home() -> list[dict]:
    """The placements in grid order. A row edited by hand may point at a parent that is gone or loop: it falls back to the top."""
    db = connect()
    try:
        rows = [dict(r) for r in db.execute("SELECT * FROM home ORDER BY position, rowid")]
    finally:
        db.close()
    ids = {r["id"] for r in rows}
    by = {r["id"]: r for r in rows}
    for r in rows:
        seen, p = {r["id"]}, r["parent_id"]
        while p:
            if p not in ids or p in seen:
                r["parent_id"] = None
                break
            seen.add(p)
            p = by[p]["parent_id"]
        r["span"] = max(1, min(3, int(r["span"] or 1)))
        r["src"] = src_of(r)
        r["chrome"] = r["widget_id"] != LOGO_ID
    return rows


def snapshot() -> str:
    return json.dumps({"widgets": list_home()}, ensure_ascii=False, sort_keys=True)


async def changes(rust_timeout: int = 5000):
    """The Home as JSON every time it differs: once at the start, then after any write to the db file or its -wal,
    whoever made it (a route, or the owner in a SQLite app). watchfiles = FSEvents, no polling loop; the timeout
    tick only re-checks, as a safety net."""
    from watchfiles import awatch

    name = db_path().name
    last = snapshot()
    yield last
    async for batch in awatch(db_path().parent, debounce=30, step=20, rust_timeout=rust_timeout, yield_on_timeout=True):
        if batch and not any(Path(p).name.startswith(name) for _, p in batch):
            continue
        cur = await asyncio.to_thread(snapshot)
        if cur != last:
            last = cur
            yield cur


# --- widgets ---------------------------------------------------------------------------------------------------
def widget_name(fn) -> str:
    return "".join(w.capitalize() for w in fn.__name__.split("_"))


def collect(domains: dict) -> list[dict]:
    """Every registered widget of the loaded projects ({slug: module}), the way the console names them."""
    out, seen = [], set()
    for slug, mod in domains.items():
        roles: dict = {}
        for module, (ev, wn) in (getattr(mod, "MODULE_WIDGETS", None) or {}).items():
            roles.setdefault((ev, wn), []).append(f"module:{module}")
        for part, wn in (getattr(mod, "ENTITY_PARTS", None) or {}).items():
            roles.setdefault(("*", wn), []).append(f"entity_part:{part}")
        home, parts_done = getattr(mod, "HOME", None), set()

        def add(kind, ev, fn, pos):
            try:
                code, file, line = inspect.getsource(fn), inspect.getsourcefile(fn), inspect.getsourcelines(fn)[1]
            except (TypeError, OSError):
                code, file, line = None, None, None
            wn = widget_name(fn) if hasattr(fn, "__name__") else repr(fn)
            r = list(roles.get((ev, wn), []))
            if ("*", wn) in roles and wn not in parts_done:  # a sidebar part: only on the first event it appears
                r += roles[("*", wn)]
                parts_done.add(wn)
            if home is not None and (home == wn or getattr(home, "__name__", None) == getattr(fn, "__name__", "")):
                r.append("home")
            wid = f"{slug}/{ev}/{wn}"
            if wid in seen:
                wid += f"#{pos}"
            seen.add(wid)
            out.append({"id": wid, "domain": slug, "event": ev, "name": wn, "kind": kind, "position": pos,
                        "function": getattr(fn, "__name__", None), "module": getattr(fn, "__module__", None), "file": file,
                        "line": line, "fake": int(bool(getattr(fn, "fake", False))), "roles": json.dumps(r), "code": code,
                        "code_sha256": hashlib.sha256(code.encode()).hexdigest() if code else None,
                        "project": getattr(mod, "__file__", None)})

        for ev, fns in (getattr(mod, "WIDGETS", None) or {}).items():
            for i, fn in enumerate(fns if isinstance(fns, (list, tuple)) else [fns]):
                add("widget", ev, fn, i)
        for i, (_n, fn) in enumerate((getattr(mod, "EXPECTED_WIDGETS", None) or {}).items()):
            add("expected", "expected", fn, i)
    return out


WCOLS = ("id", "domain", "event", "name", "kind", "position", "function", "module", "file", "line", "fake", "roles", "code",
         "code_sha256", "project")


def sync_widgets(domains: dict) -> bool:
    """Make `widgets` mirror the loaded projects. Writes only when something differs; True when it did."""
    rows = collect(domains)
    db = connect()
    try:
        db.executescript(SCHEMA)
        have = {r["id"]: tuple(r[c] for c in WCOLS) for r in db.execute(f"SELECT {','.join(WCOLS)} FROM widgets")}
        want = {r["id"]: tuple(r[c] for c in WCOLS) for r in rows}
        if have == want:
            return False
        t = now()
        with db:
            db.execute("DELETE FROM widgets")
            db.executemany(f"INSERT INTO widgets ({','.join(WCOLS)}, exported_at) VALUES ({','.join('?' * len(WCOLS))}, ?)",
                           [(*w, t) for w in want.values()])
        return True
    finally:
        db.close()
