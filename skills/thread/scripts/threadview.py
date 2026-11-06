# /// script
# dependencies = ["rich"]
# ///
"""threadview.py <hermes-session-id> — the thread view, talking to the real Hermes session headless.
Input -> `hermes -p bili --resume <sid> -z <wrapped>`; the agent's chat text is discarded,
its only output is view.json (through view.py), which this screen redraws on change.
Keys: ⏎ send · ctrl+l labels · ctrl+c quit."""
import json, os, shutil, sqlite3, subprocess, sys, termios, time, tty, select
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = os.path.expanduser(os.environ.get("THREADVIEW_DIR", "~/.local/state/threadview"))
TOURNAMENT = os.path.normpath(os.path.join(HERE, "..", "..", "choice", "scripts", "tournament.py"))
SID = sys.argv[1]
PROFILE = os.environ.get("TV_PROFILE", "bili")
DB = os.path.expanduser(f"~/.hermes/profiles/{PROFILE}/state.db")
VIEW = os.path.join(VIEWS, f"{SID}.json")
VIEWPY = os.path.join(HERE, "view.py")
LOG = os.path.join(VIEWS, f"{SID}.hermes.log")
BORDO, DIM, ACC = "#800020", "grey50", "#d7875f"
c = Console()
LABELS = [False]

WRAP = """[thread view] Gabriel digitou na thread view: «{msg}»

Você é o agente normal desta thread e pode fazer qualquer coisa, mas a prioridade é a TELA da thread: é por ela que ele conversa com você. Ninguém lê o seu texto de chat.
- Mude a tela com: python3 {viewpy} {sid} <comando>  (help e get mostram tudo). Curta, para um humano: goal, steps, artifacts, decision, pulse.
- O seu turno tem que acabar em até 10 segundos. Atualize a tela primeiro.
- Trabalho que passa de 10 s (gerar, codar, buildar) vai para um worker: registre com `worker add <id> "<o que faz>"`, rode em background desacoplado (nohup … &) e faça o comando terminar chamando `worker done <id> "<resultado>"` (ou `worker fail`). Ele aparece na fila Agentes, no topo da tela.
- No texto, fale das opções pelo NOME (nunca letra nem número: a numeração muda pelo ranking). Sem artefato "comparativo": a galeria já compara.
- Escolher entre opções (logo, tela, nome, texto) é um torneio: siga a skill choice (rode python3 {tourn} …, com --thread {sid}). Mensagem "torneio <slug>: …" é a resposta do dono a uma rodada, já registrada pela tela: não rode answer de novo; desenhe a próxima rodada (worker) e chame round.
- Opção da decisão = "<key do artefato> · <nome>". O view.py renumera tudo por ranking: 01 é sempre a mais recomendada, e os artefatos seguem o mesmo número.
- Decisão com opções: cada opção leva o seu % de certeza, somando 100 (--option "<rótulo>" <pct>); a primeira é sempre a recomendada.
- Artefato com "path" ganha galeria HTML sozinho; a URL aparece na tela.
Termine com uma palavra: ok."""

def db_max_user_id():
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        r = con.execute("select coalesce(max(id),0) from messages where session_id=? and role='user'", (SID,)).fetchone()
        con.close(); return r[0]
    except Exception: return 0

def load_view():
    try:
        with open(VIEW) as f: return json.load(f)
    except Exception: return {"goal": {"title": "(sem tela ainda)", "subtitle": ""}, "steps": [], "artifacts": [], "decision": None, "pulse": ""}

def tag(r, name):
    if not LABELS[0]: return r
    g = Table.grid(expand=True); g.add_column(ratio=1); g.add_column(width=12, justify="right")
    g.add_row(r, Text(name, style="italic magenta")); return g

def section(name, on=False): return Text.assemble(("● " if on else "", ACC), (name.upper(), f"bold {ACC}" if on else f"bold {DIM}"))

MARK = {"done": ("✓", "green"), "doing": ("◐", ACC), "blocked": ("■", f"bold {BORDO}"), "todo": ("○", DIM)}

def body(v, flash={}):
    fl = lambda k: ("● ", ACC) if k in flash else ("", "")
    parts = []
    ws = [w for w in v.get("workers", []) if w.get("state") == "running" or time.time() - (w.get("ended_at") or 0) < 15]
    if ws:
        wt = Table.grid(expand=True, padding=(0, 1)); wt.add_column(width=1); wt.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        wt.add_column(justify="right"); wt.add_column(width=5, justify="right")
        for w in ws:
            st = w.get("state")
            if st == "running" and w.get("pid"):
                try: os.kill(w["pid"], 0)
                except OSError: st = "lost"
            glyph = {"running": ("◐◓◑◒"[int(time.time() * 3) % 4], ACC), "done": ("✓", "green"), "fail": ("✗", "red"), "lost": ("?", "red")}[st]
            end = w.get("ended_at") or time.time()
            wt.add_row(Text(*glyph), Text(w.get("what", w["id"]), "" if st == "running" else DIM),
                       Text(w.get("note", "") if st != "lost" else "sumiu", DIM), Text(ago(end - w["started_at"]), DIM))
        parts += [section("agentes", "workers" in flash), tag(wt, "Agents"), Text()]
    g = v.get("goal") or {}
    title = Text.assemble(fl("goal"), ("▍", ACC), (" " + (g.get("title") or ""), "bold bright_white"))
    if g.get("subtitle"): title.append("\n  " + g["subtitle"], style=f"italic {DIM}")
    parts += [tag(title, "Goal"), Text()]
    if v.get("steps"):
        st = Table.grid(padding=(0, 1), expand=True); st.add_column(width=2); st.add_column(no_wrap=True); st.add_column(justify="right", ratio=1, no_wrap=True, overflow="ellipsis")
        for s in v["steps"]:
            m, sty = MARK.get(s.get("state", "todo"), MARK["todo"])
            todo = s.get("state", "todo") == "todo"
            st.add_row(Text(m, sty), Text(s.get("text", ""), DIM if todo else ("bold" if s.get("state") in ("doing", "blocked") else "")),
                       Text(s.get("note", ""), BORDO if s.get("state") == "blocked" else DIM))
        parts += [section("passos", "steps" in flash), tag(st, "Steps"), Text()]
    if v.get("artifacts"):
        sl = Table.grid(padding=(0, 2))
        for _ in range(4 if (v.get("decision") or {}).get("options") else len(v["artifacts"])): sl.add_column(justify="center")
        cells = []
        keys = {o["label"].split("·")[0].strip() for o in ((v.get("decision") or {}).get("options") or []) if isinstance(o, dict)}
        for a in sorted([a for a in v["artifacts"] if not keys or a.get("key", "") in keys], key=lambda a: a.get("key", "")):
            if a.get("state") == "drawing":  # a wave across the slots while the challengers are drawn
                ph = int(time.time() * 6) + 2 * cells.__len__()
                fill = ("░▒▓█▓▒"[ph % 6] + "░▒▓█▓▒"[(ph + 1) % 6], ACC)
            else:
                fill = ("▓▓", "green") if a.get("state") == "ready" else ("░░", DIM)
            name = a.get("name", "").split(":")[0].split("(")[0].strip()[:12]
            rec = "recomend" in a.get("name", "").lower()
            cells.append(Text.assemble(("┌────┐\n│ ", ACC if rec else DIM), fill, (" │\n└────┘\n", ACC if rec else DIM),
                                       (a.get("key", ""), "bold"), (f" {name}", ACC if rec else DIM), (" ★" if rec else "", ACC)))
        sl.add_row(*cells)
        parts += [section("artefatos", "artifacts" in flash), tag(sl, "Artifacts")]
        if v.get("url"):
            parts.append(tag(Text.assemble(("↗ ", ACC), (f"o · {OPEN_LABEL}", f"underline {ACC} link {v['url']}"),
                                           (f"  {v['url'].replace(os.path.expanduser('~'), '~')[-48:]}", DIM)), "Link"))
        parts.append(Text())
    d = v.get("decision")
    if d and (d.get("options") or d.get("keys")) and POLL["live"]: d = None  # the input became the poll
    if d:
        t = Text(d.get("text", ""), style="bold")
        if d.get("cmd"): t.append("\n\n"); t.append(d["cmd"], style=f"bold {ACC}")
        if d.get("options"):
            t.append("\n\n")
            for i, o in enumerate(d["options"], 1): t.append(f" {i} {label(o)} ", style="black on cyan" if i > 1 else "black on green"); t.append("  ")
        parts += [tag(Panel(t, title="◆ com você" + (" · novo" if "decision" in flash else ""), title_align="left", border_style=BORDO, box=box.HEAVY, padding=(0, 1)), "Decision"), Text()]
    if v.get("pulse") and not drawing(v):
        parts.append(tag(Text.assemble(("◌ ", ACC if "pulse" in flash else DIM), (v["pulse"], ACC if "pulse" in flash else DIM)), "Pulse"))
    return Group(*parts)

SECTIONS = {"workers": "agentes", "goal": "título", "steps": "passos", "artifacts": "artefatos", "decision": "decisão", "pulse": "pulse"}
QFILE = os.path.join(VIEWS, f"{SID}.queue.json")
BUDGET = 10  # the thread agent's turn must end within this; past it, the answer only counts once logged
OVERRUN = os.path.join(VIEWS, f"{SID}.overrun.log")
LINGER = 5  # seconds an answered card stays, so you see it land, then it leaves the stack

def ago(s):
    s = int(s); return f"{s}s" if s < 60 else f"{s // 60}:{s % 60:02d}"

def running(it): return it.get("proc") is not None and it["proc"].poll() is None

def line(it):
    """One message = one line above the input: glyph · text · ticks · timer. Answered → leaves."""
    now = time.time()
    if it["state"] == "queued":
        glyph, gs, ticks, ts, timer, txt = "⋯", DIM, "", DIM, ago(now - it["at"]), DIM
    elif it.get("failed"):
        glyph, gs, ticks, ts, timer, txt = "✗", "red", "falhou", "red", ago(it["done_at"] - it["sent_at"]), DIM
    elif it.get("done_at"):
        ch = it.get("changed")
        glyph, gs, ticks, ts, timer, txt = "✓", "green", ("↻ " + ", ".join(ch)) if ch else "sem mudança", ACC if ch else DIM, ago(it["done_at"] - it["sent_at"]), DIM
        if it.get("over"): glyph, gs, ticks, ts = "⚠", ACC, ticks + " · log", ACC
    else:
        glyph, gs = "◐◓◑◒"[int(now * 3) % 4], ACC
        ticks, ts = ("✓✓", "green") if it["read"] else ("✓", "green")
        timer, txt = ago(now - it["sent_at"]), "bright_white"
        if now - it["sent_at"] > BUDGET: glyph, gs = "◆", "bold " + ACC
    g = Table.grid(expand=True, padding=(0, 1))
    g.add_column(width=1); g.add_column(ratio=1, no_wrap=True, overflow="ellipsis"); g.add_column(justify="right"); g.add_column(width=5, justify="right")
    late = it["state"] == "sent" and (it.get("done_at") or now) - it["sent_at"] > BUDGET
    g.add_row(Text(glyph, gs), Text(it["msg"], txt), Text(ticks, ts), Text(timer, ACC if late else DIM))
    return g

def stack(q):
    return tag(Group(*[line(it) for it in q]), "Queue") if q else None

POLL = {"sel": 0, "answered": None, "live": False, "prefix": ""}
HAS_DEVC = bool(shutil.which("devc"))
OPEN_LABEL = "abrir no dev-console" if HAS_DEVC else "abrir no navegador"

def open_url(url):
    cmd = ["devc", "open", url] if HAS_DEVC else ["open", url]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

KEYNAME = {"enter": "⏎"}

def record(d, hit, text=""):
    """A tournament edge is deterministic: the screen records the answer at once (and draws the in-between state);
    the agent only draws the next round."""
    if d.get("tournament") and hit.get("answer") and os.path.exists(TOURNAMENT):
        subprocess.Popen([sys.executable, TOURNAMENT, "answer", d["tournament"], hit["answer"], *([text] if text else [])],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def poll_of(v):
    d = v.get("decision")
    if not d or not (d.get("options") or d.get("keys")): return None
    if json.dumps(d, sort_keys=True) == POLL["answered"]: return None
    return d

def label(o): return o["label"] if isinstance(o, dict) else o

def num(o, i):
    """The option's own number (01..): its leading token when numeric, else its position."""
    k = label(o).split("·")[0].strip()
    return int(k) if k.isdigit() else i + 1

def name(o):
    l = label(o); return l.split("·", 1)[1].strip() if "·" in l and l.split("·")[0].strip().isdigit() else l

def edges_panel(d, v):
    """Fixed keys, one per process edge: the same key always walks the same edge (muscle memory)."""
    t = Text(d.get("text", ""), style="bold")
    t.append("\n")
    rows = list(d["keys"]) + ([{"key": "o", "label": OPEN_LABEL}] if v.get("url") else [])
    for i, k in enumerate(rows):
        t.append(f"\n  {KEYNAME.get(k['key'], k['key']):>2}  ", style=f"bold {ACC}" if i == 0 else "bold")
        t.append(k["label"], style="bold bright_white" if i == 0 else "")
    return Panel(t, title="◆ com você", title_align="left", border_style=BORDO, box=box.HEAVY, padding=(0, 1))

def poll_panel(d, v):
    if d.get("keys"): return edges_panel(d, v)
    t = Text(d.get("text", ""), style="bold")
    if d.get("cmd"): t.append(f"\n{d['cmd']}", style=f"bold {ACC}")
    t.append("\n")
    w = max(len(name(o)) for o in d["options"])
    for i, o in enumerate(d["options"]):
        on = i == POLL["sel"]
        t.append(f"\n {'❯' if on else ' '} ", style=f"bold {ACC}" if on else DIM)
        t.append(f"{num(o, i):02d}  ", style=f"bold {ACC}" if on else "bold")
        t.append(name(o).ljust(w), style="bold bright_white" if on else "")
        if isinstance(o, dict) and "pct" in o:
            n = round(o["pct"] / 10)
            t.append("  " + "█" * n, style=ACC if i == 0 else "grey62"); t.append("░" * (10 - n), style="grey30")
            t.append(f" {o['pct']:>3}%", style=f"bold {ACC}" if i == 0 else DIM)
        if i == 0: t.append("  recomendado", style=f"italic {DIM}")
    keys = "j/k mover · ⏎ enviar" + (f" · o {OPEN_LABEL}" if v.get("url") else "") + " · i responder outra coisa"
    return Panel(t, title="◆ com você", title_align="left", subtitle=keys, subtitle_align="left",
                 border_style=BORDO, box=box.HEAVY, padding=(0, 1))

PEND = {"since": None}

def drawing(v): return any(a.get("state") == "drawing" for a in (v or {}).get("artifacts", []))

def waiting_panel(v):
    """Between rounds the input is the moment itself: what is being drawn, moving, with its time."""
    if not PEND["since"]: PEND["since"] = time.time()
    el = time.time() - PEND["since"]
    spin = "◐◓◑◒"[int(time.time() * 4) % 4]
    dots = "·" * (int(time.time() * 2) % 4)
    t = Text.assemble((f"{spin} ", f"bold {ACC}"), ((v.get("pulse") or "desenhando a próxima rodada"), "bold bright_white"),
                      (f" {dots:<3}", ACC), (f"  {ago(el)}", ACC if el > BUDGET else DIM))
    t.append("\nnada a decidir agora · a rodada nova aparece aqui sozinha · digite para outra coisa", style=DIM)
    return Panel(t, box=box.ROUNDED, border_style=ACC, padding=(0, 1))

def footer(buf, q, v=None):
    if drawing(v) and not buf and not POLL["prefix"]:
        return Group(*([stack(q)] if q else []), tag(waiting_panel(v), "Waiting"),
                     tag(Text.assemble((SID[-6:], "cyan"), (f"  {PROFILE}", DIM), justify="right"), "Hints"))
    PEND["since"] = None if not drawing(v) else PEND["since"]
    d = poll_of(v or {}) if not buf else None
    POLL["live"] = bool(poll_of(v or {}))
    if d:
        return Group(*([stack(q)] if q else []), tag(poll_panel(d, v), "Poll"),
                     tag(Text.assemble((SID[-6:], "cyan"), (f"  {PROFILE}", DIM), justify="right"), "Hints"))
    inp = Panel(Text.assemble(("❯ ", f"bold {ACC}"), (buf, ""), ("" if buf else ("feedback para a próxima rodada" if POLL["prefix"].strip() else ("responder outra coisa" if POLL["prefix"] else "qualquer pedido")), DIM), ("▌", "blink")),
                box=box.ROUNDED, border_style=DIM, padding=(0, 1))
    hint = Table.grid(expand=True); hint.add_column(); hint.add_column(justify="right")
    hint.add_row(Text("⏎ empilhar · ctrl+l rótulos · ctrl+c sair", style=DIM),
                 Text.assemble((SID[-6:], "cyan"), (f"  {PROFILE}", DIM)))
    return Group(*([stack(q)] if q else []), tag(inp, "Input"), tag(hint, "Hints"))

def footer_height(q, v=None, buf=""):
    if drawing(v) and not buf and not POLL["prefix"]: return len(q) + 4 + 1
    d = poll_of(v or {}) if not buf else None
    if d and d.get("keys"): return len(q) + 2 + 1 + 1 + len(d["keys"]) + (1 if (v or {}).get("url") else 0) + 1
    if d: return len(q) + 2 + 1 + (1 if d.get("cmd") else 0) + 1 + len(d["options"]) + 1
    return 4 + len(q)

def view(v, buf, q, flash):
    lay = Layout()
    lay.split_column(Layout(Panel(body(v, flash), box=box.SIMPLE, padding=(0, 1)), name="body"),
                     Layout(footer(buf, q, v), name="input", size=min(footer_height(q, v, buf), c.height - 6)))
    return lay

def dispatch(it):
    it["base"] = db_max_user_id()
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    log = open(LOG, "a"); log.write(f"\n=== {time.ctime()} {it['msg']}\n"); log.flush()
    it["proc"] = subprocess.Popen(["hermes", "-p", PROFILE, "--resume", SID, "-z", WRAP.format(msg=it["msg"], viewpy=VIEWPY, sid=SID, tourn=TOURNAMENT)],
                                  stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    it.update(state="sent", sent_at=time.time(), read=False, changed=[], before=load_view())

def persist(q):  # only what still waits survives a restart
    with open(QFILE, "w") as f:
        json.dump([{"msg": it["msg"], "at": it["at"]} for it in q if it["state"] == "queued"], f, ensure_ascii=False)

def restore():
    try:
        with open(QFILE) as f: return [{"msg": d["msg"], "at": d["at"], "state": "queued"} for d in json.load(f)]
    except Exception: return []

fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
buf, q, v, mt, flash = "", restore(), load_view(), 0, {}
try:
    tty.setcbreak(fd)
    with Live(view(v, buf, q, flash), console=c, screen=True, auto_refresh=False) as live:
        while True:
            if select.select([fd], [], [], 0.25)[0]:
                data = os.read(fd, 1024).decode(errors="ignore")
                d = poll_of(v) if not (buf or POLL["prefix"]) else None
                if data == "\x1b": buf = ""; POLL["prefix"] = ""; data = ""
                elif data.startswith("\x1b"): data = ""
                elif d and data == "o" and v.get("url"): open_url(v["url"]); data = ""
                elif d and d.get("keys"):  # edges: a fixed key per edge
                    hit = next((k for k in d["keys"] if (k["key"] == "enter" and data in ("\r", "\n")) or k["key"] == data), None)
                    if hit and hit.get("type"): POLL["prefix"] = hit["send"]; POLL["edge"] = (d, hit); data = ""
                    elif hit:
                        record(d, hit)
                        q.append({"msg": hit["send"], "at": time.time(), "state": "queued"})
                        POLL["answered"] = json.dumps(d, sort_keys=True); persist(q); data = ""
                    else: data = ""
                elif d:  # a choice: vi keys
                    n = len(d["options"])
                    if data in ("k", "\x1b[A"): POLL["sel"] = (POLL["sel"] - 1) % n; data = ""
                    elif data in ("j", "\x1b[B"): POLL["sel"] = (POLL["sel"] + 1) % n; data = ""
                    elif data == "i": POLL["prefix"] = " "; data = ""
                    elif data in ("\r", "\n"):
                        i = POLL["sel"]
                        q.append({"msg": f"escolhi {num(d['options'][i], i):02d}: {name(d['options'][i])}", "at": time.time(), "state": "queued"})
                        POLL["answered"], POLL["sel"] = json.dumps(d, sort_keys=True), 0; persist(q); data = ""
                    else: data = ""
                for ch in data:
                    if ch in ("\n", "\r"):
                        if buf.strip():
                            q.append({"msg": (POLL["prefix"].strip() + " " + buf.strip()).strip(), "at": time.time(), "state": "queued"})
                            if POLL.get("edge"): record(POLL["edge"][0], POLL["edge"][1], buf.strip()); POLL["edge"] = None
                            if POLL["prefix"] and poll_of(v): POLL["answered"] = json.dumps(v["decision"], sort_keys=True)
                            buf = ""; POLL["prefix"] = ""; persist(q)
                    elif ch in ("\x7f", "\b"): buf = buf[:-1]
                    elif ch == "\x0c": LABELS[0] = not LABELS[0]
                    elif ch.isprintable(): buf += ch
            now = time.time()
            for it in q:
                if it["state"] != "sent": continue
                if not it["read"] and db_max_user_id() > it["base"]: it["read"] = True
                code = it["proc"].poll()
                if code is not None and not it.get("done_at") and not it.get("failed"):
                    if code == 0: it["done_at"] = now
                    else: it["failed"], it["done_at"] = True, now
                    took = now - it["sent_at"]
                    if took > BUDGET:
                        with open(OVERRUN, "a") as f:
                            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "secs": round(took, 1), "budget": BUDGET,
                                                "msg": it["msg"], "changed": it.get("changed", []), "exit": code}, ensure_ascii=False) + "\n")
                        it["over"] = True
            # answered → leaves the stack (after a short linger); one turn at a time, in order
            q = [it for it in q if not (it.get("done_at") and now - it["done_at"] > (LINGER * 3 if it.get("failed") else LINGER))]
            if q and not any(running(it) for it in q):
                nxt = next((it for it in q if it["state"] == "queued"), None)
                if nxt: dispatch(nxt); persist(q)
            try: m = os.path.getmtime(VIEW)
            except OSError: m = 0
            if m != mt:
                nv = load_view()
                if mt:
                    for k in SECTIONS:
                        if nv.get(k) != v.get(k): flash[k] = now
                    for it in q:
                        if running(it):
                            it["changed"] = [SECTIONS[k] for k in SECTIONS if nv.get(k) != it["before"].get(k)]
                mt, v = m, nv
            flash = {k: t for k, t in flash.items() if now - t < 6}
            live.update(view(v, buf, q, flash), refresh=True)
except KeyboardInterrupt:
    pass
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    persist(q)
    for it in q:
        if running(it): it["proc"].terminate()
