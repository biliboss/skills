"""The Agents module of the dev-console: what the owner typed to the agents, and the agents' session logs, in real time.

Sibling of dev-console.py (which only mounts the routes and the page shell). Three parts:
  - a SOURCE (discovery + a line normalizer): Claude Code today; pi (~/.pi/agent/sessions) and Hermes
    (~/.hermes/profiles/*/sessions) are added by writing another class with the same two methods and listing it in SOURCES;
  - the HUB: one background tailer for every client (one thread). The trigger is an EVENT: watchfiles (FSEvents on macOS)
    says which .jsonl changed and the hub reads it from its stored offset (~50 ms from the write to the entry). A
    safety net rescans the roots and checks every file every ~5 s (it catches what a lost event left). If watchfiles
    cannot be imported the hub polls every ~1 s instead and says so (`mode` = "poll", one warning line on the page).
    Two in-memory rings. Nothing is written to
    disk and no entry text is ever printed or logged: these logs hold the owner's private prompts;
  - the page script (AGENTS_JS), which renders every text with textContent, never innerHTML.

Entry (normalized): {id, t (ISO), session (short), project, kind, text (short), more (bool), side (bool)}; `id` is
`<file-key>:<byte offset of the line>`, so a client can resume after a reload (SSE Last-Event-ID).
kind: prompt | cross | notification | other | assistant | tool.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ENV_DIRS = "DEV_CONSOLE_AGENTS_DIRS"
MAX_LINE = 1_000_000  # above this a line is an api-request-blob (type api-request-blob at its beginning): skipped, never parsed
SHORT = 600  # the text a list row carries; the whole text comes from /agents/api/entry
FULL = 50_000  # cap of the whole text of one entry
PROMPT_KINDS = ("prompt", "cross", "notification", "other")  # what the Prompts view may show (prompt is the default)
WANT_PROMPTS, WANT_LOG = 200, 500  # the backfill reads the tail of the newest files until it has about this many
RING_PROMPTS, RING_LOG = 2000, 5000
TICK, RESCAN, KEEPALIVE = 1.0, 5.0, 15.0
READ_CAP = 4_000_000  # bytes read from one file per tick (a bigger burst continues on the next tick)



def iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _clip(s: str, n: int) -> tuple[str, bool]:
    return (s[:n], len(s) > n)


def _blocks_text(content: list) -> str:
    """Text blocks joined, and a marker such as [image] for each block that is not text (an image or a paste)."""
    out = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
            out.append(b["text"])
        elif isinstance(b, dict):
            out.append(f"[{b.get('type', 'block')}]")
    return "\n".join(out)


@dataclass
class FileState:
    path: Path
    key: str  # a hash of the realpath: the id never carries a path
    source: str
    session: str  # short id, from the file name
    project: str  # folder name until a line says its cwd
    side_file: bool  # agent-*.jsonl: a sub-agent's own file
    offset: int = 0  # start of the first byte not yet parsed (always at a line start)
    seen_size: int = -1
    seen_mtime: float = 0.0
    resync: bool = False  # offset may be mid-line: drop bytes up to the first newline
    gone: bool = False
    mtime: float = 0.0


class ClaudeSource:
    """Claude Code: ~/.claude/projects/<project-dir>/<session-id>.jsonl (one JSON object per line)."""

    name = "claude"

    def discover(self, roots: Iterable[Path]) -> Iterable[Path]:
        for root in roots:
            try:
                for proj in os.scandir(root):
                    if not proj.is_dir():
                        continue
                    for f in os.scandir(proj.path):
                        if f.name.endswith(".jsonl") and f.is_file():
                            yield Path(f.path)
            except OSError:
                continue

    def describe(self, path: Path) -> tuple[str, str, bool]:
        stem = path.stem
        side = stem.startswith("agent-")
        return (("ag:" + stem[6:12]) if side else stem[:8], path.parent.name, side)

    def normalize(self, raw: bytes, offset: int, fs: FileState, full: bool = False) -> dict | None:
        """One log line -> an entry, or None (noise, a garbled line, a line above MAX_LINE). Never raises."""
        if len(raw) > MAX_LINE:
            return None  # the beginning says "type":"api-request-blob" or a huge paste: neither is worth a json.loads
        try:
            d = json.loads(raw)
        except (ValueError, RecursionError):
            return None
        if not isinstance(d, dict):
            return None
        typ = d.get("type")
        cwd = d.get("cwd")
        if isinstance(cwd, str) and cwd:
            fs.project = cwd.rstrip("/").rsplit("/", 1)[-1] or cwd
        msg = d.get("message") if isinstance(d.get("message"), dict) else {}
        content = msg.get("content")
        cap = FULL if full else SHORT
        if typ == "user":
            kind, text = self._user(d, content)
            if kind is None:
                return None
        elif typ == "assistant" and isinstance(content, list):
            texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
            tools = [str(b.get("name", "tool")) for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
            if texts:
                kind, text = "assistant", "\n".join(texts)
            elif tools:
                kind, text = "tool", ", ".join(tools)
            else:
                return None
        else:
            return None
        text, more = _clip(text, cap)
        ts = d.get("timestamp")
        return {
            "id": f"{fs.key}:{offset}", "t": ts if isinstance(ts, str) else iso_from_ts(fs.mtime or time.time()),
            "session": fs.session, "project": fs.project, "kind": kind, "text": text, "more": more,
            "side": bool(d.get("isSidechain")) or fs.side_file,
        }

    @staticmethod
    def _user(d: dict, content) -> tuple[str | None, str]:
        """The allow-list: a `prompt` is exactly origin.kind == "human" and promptSource == "typed". peer and
        task-notification have their own kinds; anything unknown is `other`, never `prompt`."""
        origin = d.get("origin") if isinstance(d.get("origin"), dict) else None
        okind = origin.get("kind") if origin else None
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                return None, ""  # a tool's answer: noise in both views
            text = _blocks_text(content)
        else:
            return None, ""
        if okind == "human" and d.get("promptSource") == "typed":
            return "prompt", text
        if okind == "peer":
            who = next((origin[k] for k in ("name", "from") if isinstance(origin.get(k), str)), "")
            return "cross", (f"{who}: " if who else "") + (origin["body"] if isinstance(origin.get("body"), str) else text)
        if okind == "task-notification":
            return "notification", text
        return "other", text


SOURCES = {"claude": ClaudeSource()}  # pi and Hermes: one class each (discover, describe, normalize), added here


def roots_from_env() -> list[Path]:
    """The configured roots, deduplicated by realpath (~/.claude-mukutu/projects is a symlink to ~/.claude/projects)."""
    raw = os.environ.get(ENV_DIRS) or str(Path.home() / ".claude" / "projects")
    seen, out = set(), []
    for p in raw.split(os.pathsep):
        if not p:
            continue
        r = Path(p).expanduser().resolve()
        if r not in seen and r.is_dir():
            seen.add(r)
            out.append(r)
    return out


class Hub:
    def __init__(self, roots: list[Path], sources: dict | None = None):
        self.roots = [r.resolve() for r in roots]
        self.sources = sources or SOURCES
        self.files: dict[str, FileState] = {}  # key -> state
        self.by_real: dict[str, str] = {}  # realpath -> key (the dedupe)
        self.prompts: deque = deque(maxlen=RING_PROMPTS)
        self.log: deque = deque(maxlen=RING_LOG)  # every entry and the reset markers, in arrival order
        self.seq = 0
        self.lock = threading.RLock()
        self.ready = threading.Event()
        self.last_scan = 0.0
        self.mode = "start"  # "watch" (events) or "poll" (watchfiles missing)
        self.stop_event = threading.Event()

    # --- discovery -------------------------------------------------------------------------------------------------
    def rescan(self) -> list[FileState]:
        """Register files not seen yet. A new file is read from its start; at the first scan files only get an offset."""
        new = []
        for sname, src in self.sources.items():
            for p in src.discover(self.roots):
                try:
                    real = str(p.resolve())
                    if real in self.by_real:
                        continue
                    st = os.stat(real)
                except OSError:
                    continue
                if not any(Path(real).is_relative_to(r) for r in self.roots):
                    continue  # never read outside the configured roots (a symlinked file pointing elsewhere)
                key = hashlib.sha1(real.encode()).hexdigest()[:8]
                sess, proj, side = src.describe(Path(real))
                fs = FileState(Path(real), key, sname, sess, proj, side, mtime=st.st_mtime)
                if self.ready.is_set():  # born after the backfill: its whole content is new
                    fs.offset, fs.seen_size = 0, -1
                with self.lock:
                    self.files[key] = fs
                    self.by_real[real] = key
                new.append(fs)
        self.last_scan = time.time()
        return new

    # --- reading ---------------------------------------------------------------------------------------------------
    def _read(self, fs: FileState, start: int, end: int) -> bytes:
        with open(fs.path, "rb") as f:
            f.seek(start)
            return f.read(end - start)

    def _lines(self, data: bytes, base: int) -> tuple[list[tuple[int, bytes]], int]:
        """Complete lines with their absolute offsets, and the offset where the unfinished last line (if any) starts."""
        out, pos = [], 0
        while True:
            nl = data.find(b"\n", pos)
            if nl < 0:
                return out, base + pos  # a partial last line is kept for the next read, never parsed
            if nl > pos:
                out.append((base + pos, data[pos:nl]))
            pos = nl + 1

    def backfill_file(self, fs: FileState, want_prompts: int, want_log: int) -> list[dict]:
        """The tail of one file: windows from the end, doubling, until it holds enough entries. Sets the offset."""
        try:
            st = os.stat(fs.path)
        except OSError:
            fs.gone = True
            return []
        size = st.st_size
        win, entries = 256 * 1024, []
        while True:
            start = max(0, size - win)
            data = self._read(fs, start, size)
            if start > 0:  # the window began mid-line: drop that piece
                cut = data.find(b"\n")
                if cut < 0:
                    data, start = b"", size
                else:
                    data, start = data[cut + 1:], start + cut + 1
            lines, tail_off = self._lines(data, start)
            entries = [e for e in (self.sources[fs.source].normalize(r, o, fs) for o, r in lines) if e]
            n_p = sum(e["kind"] == "prompt" for e in entries)
            if start == 0 or win >= 8 * 1024 * 1024 or (n_p >= want_prompts or len(entries) >= want_log):
                break
            win *= 4
        fs.offset, fs.seen_size, fs.seen_mtime, fs.resync = tail_off, size, st.st_mtime, False
        return entries

    def backfill(self) -> None:
        """Newest files first, tail only, until about WANT_PROMPTS prompts and WANT_LOG entries. Older files get only an
        offset at their end (new activity in them will still be tailed)."""
        order = sorted(self.files.values(), key=lambda f: f.mtime, reverse=True)
        got_p = got_l = 0
        everything: list[dict] = []
        for i, fs in enumerate(order):
            if (got_p >= WANT_PROMPTS and got_l >= WANT_LOG) or i >= 150:
                self._park(fs)
                continue
            es = self.backfill_file(fs, WANT_PROMPTS - got_p, WANT_LOG - got_l)
            got_p += sum(e["kind"] == "prompt" for e in es)
            got_l += len(es)
            everything += es
        everything.sort(key=lambda e: e["t"])
        with self.lock:
            for e in everything:
                self._publish(e)
        self.ready.set()

    def _park(self, fs: FileState) -> None:
        """Not read: its offset is its end; resync when that end is not at a line start."""
        try:
            st = os.stat(fs.path)
            fs.offset, fs.seen_size, fs.seen_mtime = st.st_size, st.st_size, st.st_mtime
            if st.st_size:
                fs.resync = self._read(fs, st.st_size - 1, st.st_size) != b"\n"
        except OSError:
            fs.gone = True

    def _publish(self, e: dict) -> None:
        self.seq += 1
        e = {**e, "_seq": self.seq, "_f": e["id"].split(":", 1)[0]}
        self.log.append(e)
        if e["kind"] in PROMPT_KINDS:
            self.prompts.append(e)

    # --- tailing ---------------------------------------------------------------------------------------------------
    def tick(self) -> int:
        """Check every known file (the polling mode, and the safety net of the watch mode). Returns new entries."""
        return sum(self.check(fs) for fs in list(self.files.values()))

    def check(self, fs: FileState) -> int:
        """One file: compare size and mtime with what was read, read from the offset to the end."""
        if fs.gone:
            return 0
        try:
            st = os.stat(fs.path)
        except OSError:  # the file disappeared: its past entries stay, nothing more comes
            fs.gone = True
            return 0
        fs.mtime = st.st_mtime
        if st.st_size < fs.offset:  # shrank (rewritten): forget its entries, read it again, tell the clients
            self._reset(fs)
        if st.st_size == fs.seen_size and st.st_mtime == fs.seen_mtime:
            return 0
        return self._advance(fs, st)

    def touch(self, path: str) -> int:
        """The watcher's event for one path: register the file if it is new (inside the roots), then read it."""
        try:
            real = str(Path(path).resolve())
        except OSError:
            return 0
        if not real.endswith(".jsonl"):
            return 0
        key = self.by_real.get(real)
        if key is None:
            self.rescan()  # a new file (maybe in a new folder): discovery registers it, born after the backfill
            key = self.by_real.get(real)
        return self.check(self.files[key]) if key else 0

    def _reset(self, fs: FileState) -> None:
        with self.lock:
            self.log = deque((e for e in self.log if e["_f"] != fs.key), maxlen=RING_LOG)
            self.prompts = deque((e for e in self.prompts if e["_f"] != fs.key), maxlen=RING_PROMPTS)
            self.seq += 1
            self.log.append({"_seq": self.seq, "_f": fs.key, "kind": "reset", "id": f"{fs.key}:reset{self.seq}", "session": fs.session})
        fs.offset, fs.resync = 0, False

    def _advance(self, fs: FileState, st) -> int:
        end, start = st.st_size, fs.offset
        data = self._read(fs, start, min(end, start + READ_CAP))
        read_end = start + len(data)
        if fs.resync:  # the offset was mid-line: skip to the first line start
            cut = data.find(b"\n")
            if cut < 0:
                fs.seen_size, fs.seen_mtime = end, st.st_mtime
                return 0
            data, start, fs.resync = data[cut + 1:], start + cut + 1, False
        lines, fs.offset = self._lines(data, start)
        if read_end < end:  # a burst bigger than READ_CAP: the next tick continues
            fs.seen_size = -1
        else:
            fs.seen_size, fs.seen_mtime = end, st.st_mtime
        src = self.sources[fs.source]
        es = [e for e in (src.normalize(r, o, fs) for o, r in lines) if e]
        with self.lock:
            for e in es:
                self._publish(e)
        return len(es)

    def run(self) -> None:
        """The thread body: backfill once, then follow by events (or by polling when watchfiles is missing)."""
        self.rescan()
        self.backfill()
        try:
            from watchfiles import watch
        except ImportError:
            self.mode = "poll"
        else:
            self.mode = "watch"
        while not self.stop_event.is_set():
            try:
                if self.mode == "watch":
                    self._follow(watch)
                else:
                    self._poll_once()
            except Exception:  # one bad pass never kills the tailer; no text is logged
                self.stop_event.wait(TICK)

    def _poll_once(self) -> None:
        self.stop_event.wait(TICK)
        if time.time() - self.last_scan >= RESCAN:
            self.rescan()
        self.tick()

    def _follow(self, watch) -> None:
        self.tick()  # what was written between the backfill and the watcher's start
        # rust_timeout + yield_on_timeout: an empty batch every second, the moment for the safety net
        for changes in watch(*self.roots, debounce=50, step=20, recursive=True, stop_event=self.stop_event,
                             rust_timeout=1000, yield_on_timeout=True, raise_interrupt=False):
            for _kind, path in changes:
                self.touch(path)
            if time.time() - self.last_scan >= RESCAN:  # the net: new files and every file, in case an event was lost
                self.rescan()
                self.tick()

    def stop(self) -> None:
        self.stop_event.set()

    # --- reads (the routes' logic) ---------------------------------------------------------------------------------
    @staticmethod
    def _public(e: dict) -> dict:
        return {k: v for k, v in e.items() if not k.startswith("_")}

    def _select(self, ring, limit: int, session: str, kinds: Iterable[str] | None, side: bool) -> list[dict]:
        kinds = set(kinds) if kinds else None
        with self.lock:
            items = list(ring)
        out = [e for e in items if e["kind"] != "reset" and (kinds is None or e["kind"] in kinds)
               and (side or not e["side"]) and (not session or e["session"].startswith(session))]
        return [self._public(e) for e in out[-max(1, min(limit, 5000)):]]

    def get_prompts(self, limit=200, session="", kinds=("prompt",), side=False) -> dict:
        return {"entries": self._select(self.prompts, limit, session, kinds, side), "last": self.last_id(), "sessions": self.sessions(), "mode": self.mode}

    def get_log(self, limit=500, session="", side=False) -> dict:
        return {"entries": self._select(self.log, limit, session, None, side), "last": self.last_id(), "sessions": self.sessions(), "mode": self.mode}

    def last_id(self) -> str:
        with self.lock:
            return self.log[-1]["id"] if self.log else ""

    def sessions(self) -> list[dict]:
        """One row per session (sub-agent files folded under their own `ag:` ids), newest activity first."""
        with self.lock:
            files = list(self.files.values())
        rows = [{"session": f.session, "project": f.project, "last": iso_from_ts(f.mtime), "side": f.side_file} for f in files]
        rows.sort(key=lambda r: r["last"], reverse=True)
        return rows[:200]

    def get_entry(self, eid: str) -> dict | None:
        """The whole text of one entry (capped): re-read its line from the file; only known files, only at that offset."""
        key, _, off = eid.partition(":")
        fs = self.files.get(key)
        if not fs or not off.isdigit() or fs.gone:
            return None
        offset = int(off)
        try:
            with open(fs.path, "rb") as f:
                f.seek(offset)
                raw = f.readline(MAX_LINE + 1).rstrip(b"\n")
        except OSError:
            return None
        return self.sources[fs.source].normalize(raw, offset, fs, full=True)

    def since(self, seq: int) -> list[dict]:
        with self.lock:
            return [e for e in self.log if e["_seq"] > seq]

    def seq_of(self, eid: str) -> int | None:
        with self.lock:
            return next((e["_seq"] for e in reversed(self.log) if e["id"] == eid), None)

    def cur_seq(self) -> int:
        return self.seq


_HUB: Hub | None = None
_HUB_LOCK = threading.Lock()


def get_hub() -> Hub:
    """The one hub of the process, its thread started by the first request (the roots are read from the env then)."""
    global _HUB
    with _HUB_LOCK:
        if _HUB is None:
            _HUB = Hub(roots_from_env())
            threading.Thread(target=_HUB.run, name="agents-tailer", daemon=True).start()
        return _HUB


def ready_hub() -> Hub:
    h = get_hub()
    h.ready.wait(15)
    return h


async def sse(hub: Hub, after: str = ""):
    """Server-sent events for one client: `retry:`, then each new entry as `id: <entry id>` + `data: <json>`; a keep-alive
    comment every ~15 s. `after` (the Last-Event-ID header or ?after=) resumes; an id no longer known resumes from now."""
    cursor = hub.seq_of(after) if after else None
    if cursor is None:
        cursor = hub.cur_seq()
    yield "retry: 3000\n\n"
    quiet = 0.0
    while True:
        items = hub.since(cursor)
        for e in items:
            cursor = e["_seq"]
            if e["kind"] == "reset":
                yield f"event: reset\nid: {e['id']}\ndata: {json.dumps({'session': e['session']})}\n\n"
            else:
                yield f"id: {e['id']}\ndata: {json.dumps(Hub._public(e), ensure_ascii=False)}\n\n"
        if items:
            quiet = 0.0
        else:
            quiet += 0.1
            if quiet >= KEEPALIVE:
                quiet = 0.0
                yield ": keep-alive\n\n"
        await asyncio.sleep(0.1)  # a lock and a list scan: cheap; the stream adds <= 100 ms


AGENTS_JS = r"""
const KINDS_P = ['prompt', 'cross', 'notification', 'other'];
const SHOW = new Set((Q.get('show') || '').split(',').filter(Boolean));  // chips on: cross, notification, other, side
let view = Q.get('view') === 'log' ? 'log' : 'prompts', session = Q.get('session') || '', paused = Q.get('pause') === '1';
let P = [], L = [], SESS = [], live = false;
const keep = () => {  // all UI state lives in the query string
  const set = (k, v) => v ? Q.set(k, v) : Q.delete(k);
  set('view', view === 'log' ? 'log' : ''); set('session', session); set('show', [...SHOW].join(',')); set('pause', paused ? '1' : '');
  history.replaceState(null, '', location.pathname + (Q.toString() ? '?' + Q : ''));
};
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const hhmm = iso => { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleTimeString('pt-BR', {hour12: false}) + (d.toDateString() === new Date().toDateString() ? '' : ' ' + d.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'})); };
const pass = e => (!session || e.session.startsWith(session)) && (!e.side || SHOW.has('side'))
  && (view === 'log' ? true : e.kind === 'prompt' || SHOW.has(e.kind));
const KCLS = {prompt: 'text-neutral-900 dark:text-neutral-100 font-semibold', cross: 'text-sky-600', notification: 'text-neutral-400', other: 'text-amber-600', assistant: 'text-neutral-500', tool: 'text-neutral-400'};
function row(e) {
  const r = el('div', 'agrow px-3 py-1 border-b border-neutral-100 dark:border-neutral-900 cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-900');
  r.dataset.id = e.id;
  const head = el('div', 'flex gap-3 whitespace-nowrap');
  head.append(el('span', 'text-neutral-400 shrink-0', hhmm(e.t)), el('span', 'text-neutral-500 shrink-0', e.session),
    el('span', 'text-neutral-500 shrink-0 max-w-[14rem] truncate', e.project), el('span', 'shrink-0 ' + (KCLS[e.kind] || ''), e.kind + (e.side ? '*' : '')));
  const body = el('div', 'agtext text-neutral-800 dark:text-neutral-200 truncate', e.text + (e.more ? ' …' : ''));
  r.append(head, body);
  r.onclick = async () => {
    const open = r.classList.toggle('open');
    body.classList.toggle('truncate', !open); body.classList.toggle('whitespace-pre-wrap', open); body.classList.toggle('break-words', open);
    if (open && e.more && !e.full) {
      try { const j = await (await fetch('/agents/api/entry?id=' + encodeURIComponent(e.id))).json(); if (j.text != null) { e.full = true; body.textContent = j.text + (j.more ? ' …' : ''); } } catch (_) {}
    }
  };
  return r;
}
const list = () => $('aglist');
function nearBottom() { const l = list(); return l.scrollHeight - l.scrollTop - l.clientHeight < 80; }
function toBottom() { const l = list(); l.scrollTop = l.scrollHeight; }
function render() {
  const l = list(); l.replaceChildren();
  const src = (view === 'log' ? L : P).filter(pass);
  l.append(...src.slice(-1000).map(row));
  if (!src.length) l.append(el('p', 'px-3 py-6 text-neutral-400', 'nada ainda'));
  toBottom(); chrome();
}
function add(e) {  // a pushed entry: append in place; the page is never reloaded
  L.push(e); if (KINDS_P.includes(e.kind)) P.push(e);
  if (!pass(e)) return;
  const l = list(), stick = !paused && nearBottom();
  if (l.querySelector('p')) l.replaceChildren();
  l.append(row(e));
  while (l.childElementCount > 1000) l.firstChild.remove();
  if (stick) toBottom();
  chrome();
}
function chrome() {
  $('v-prompts').className = 'px-2 cursor-pointer ' + (view === 'prompts' ? 'text-neutral-900 dark:text-neutral-100 underline' : 'text-neutral-400');
  $('v-log').className = 'px-2 cursor-pointer ' + (view === 'log' ? 'text-neutral-900 dark:text-neutral-100 underline' : 'text-neutral-400');
  for (const c of ['cross', 'notification', 'other', 'side']) {
    const b = $('c-' + c); b.className = 'px-2 cursor-pointer rounded border ' + (SHOW.has(c) ? 'border-neutral-500 text-neutral-900 dark:text-neutral-100' : 'border-transparent text-neutral-400');
    b.style.display = c === 'side' || view === 'prompts' ? '' : 'none';
  }
  $('pause').textContent = paused ? '▶ seguir' : '❚❚ pausar'; $('live').textContent = live ? '● ao vivo' : '○ reconectando';
  $('live').className = live ? 'text-green-600' : 'text-amber-600';
}
function sessions() {
  const s = $('sess'), cur = session; s.replaceChildren(new Option('todas as sessões', ''));
  for (const x of SESS) s.append(new Option(`${x.session} · ${x.project} · ${hhmm(x.last)}`, x.session));
  if (cur && !SESS.some(x => x.session === cur)) s.append(new Option(cur, cur));
  s.value = cur;
}
async function load() {
  const q = session ? '&session=' + encodeURIComponent(session) : '', sd = '&side=1';  // side is filtered on screen by its chip
  const [p, g] = await Promise.all([
    fetch('/agents/api/prompts?limit=300&kinds=' + KINDS_P.join(',') + q + sd).then(r => r.json()),
    fetch('/agents/api/log?limit=600' + q + sd).then(r => r.json())]);
  P = p.entries; L = g.entries; SESS = g.sessions; sessions(); render();
  $('warn').textContent = g.mode === 'poll' ? 'watchfiles indisponível: seguindo por consulta a cada 1 s' : '';
  connect(g.last);
}
let es = null;
function connect(after) {
  if (es) es.close();
  es = new EventSource('/agents/events' + (after ? '?after=' + encodeURIComponent(after) : ''));
  es.onopen = () => { live = true; chrome(); };
  es.onerror = () => { live = false; chrome(); };  // EventSource retries by itself, sending Last-Event-ID
  es.onmessage = m => { try { add(JSON.parse(m.data)); } catch (_) {} };
  es.addEventListener('reset', () => load());  // a log file shrank: its old entries are gone, read the lists again
}
$('v-prompts').onclick = () => { view = 'prompts'; keep(); render(); };
$('v-log').onclick = () => { view = 'log'; keep(); render(); };
for (const c of ['cross', 'notification', 'other', 'side']) $('c-' + c).onclick = () => { SHOW.has(c) ? SHOW.delete(c) : SHOW.add(c); keep(); render(); };
$('pause').onclick = () => { paused = !paused; keep(); if (!paused) toBottom(); chrome(); };
$('sess').onchange = e => { session = e.target.value; keep(); load(); };
setInterval(() => fetch('/agents/api/log?limit=1').then(r => r.json()).then(j => { SESS = j.sessions; sessions(); }).catch(() => {}), 10000);
load();
"""
