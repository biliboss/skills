#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""fluid-voice-auto-fix engine. Called by fix.sh. Stdlib only.

Env (all optional):
  FLUID_DOMAIN       defaults domain            (default com.FluidApp.app)
  FLUID_APP_ID       bundle id to quit/reopen   (default com.FluidApp.app)
  FLUID_VOCAB        vocabulary JSON path       (default ~/Library/Application Support/FluidVoice/parakeet_custom_vocabulary.json)
  FLUID_BACKUP_DIR   where backups go           (default ~/.local/share/fluid-voice-auto-fix/backups)
  FLUID_RESTART      0 = never quit/open the app (tests)
  FLUID_HISTORY      FluidVoice TranscriptionHistory.sqlite3 path
  FLUID_CLAUDE_GLOB  Claude Code transcripts    (default ~/.claude/projects/*/*.jsonl)
  FLUID_HERMES_DBS   colon-separated state.db paths (default ~/.hermes/profiles/*/state.db and ~/.hermes/state.db)
"""
import unicodedata, base64, collections, datetime, difflib, glob, json, os, plistlib, re
import sqlite3, subprocess, sys, time, uuid

E = os.environ
HOME = os.path.expanduser("~")
DOMAIN = E.get("FLUID_DOMAIN", "com.FluidApp.app")
APP_ID = E.get("FLUID_APP_ID", "com.FluidApp.app")
SUPPORT = os.path.join(HOME, "Library/Application Support/FluidVoice")
VOCAB = E.get("FLUID_VOCAB", os.path.join(SUPPORT, "parakeet_custom_vocabulary.json"))
BACKUP_DIR = E.get("FLUID_BACKUP_DIR", os.path.join(HOME, ".local/share/fluid-voice-auto-fix/backups"))
HISTORY = E.get("FLUID_HISTORY", os.path.join(SUPPORT, "TranscriptionHistory.sqlite3"))
CLAUDE_GLOB = E.get("FLUID_CLAUDE_GLOB", os.path.join(HOME, ".claude/projects/*/*.jsonl"))
KEY = "CustomDictionaryEntries"
WEIGHT = 10


def die(msg, code=1):
    print("erro: " + msg, file=sys.stderr)
    sys.exit(code)


# ---------- dictionary (defaults) ----------
def read_entries():
    p = subprocess.run(["defaults", "export", DOMAIN, "-"], capture_output=True)
    if p.returncode != 0 or not p.stdout.strip():
        return []
    try:
        d = plistlib.loads(p.stdout)
    except Exception:
        return []
    raw = d.get(KEY)
    if not raw:
        return []
    return json.loads(raw if isinstance(raw, bytes) else raw.encode())


def write_entries(entries):
    blob = json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode()
    r = subprocess.run(["defaults", "write", DOMAIN, KEY, "-data", blob.hex()])
    if r.returncode != 0:
        die("defaults write falhou")


def read_vocab():
    if not os.path.exists(VOCAB):
        return {"alpha": 2.8, "minCombinedConfidence": 0.64, "minCtcScore": -2.2,
                "minSimilarity": 0.72, "minTermLength": 3, "terms": []}
    with open(VOCAB, encoding="utf-8") as f:
        return json.load(f)


def write_vocab(v):
    os.makedirs(os.path.dirname(VOCAB) or ".", exist_ok=True)
    tmp = VOCAB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, VOCAB)


def fmt_entries(entries):
    return [", ".join(e["triggers"]) + "  ->  " + e["replacement"] for e in entries]


def fmt_vocab(v):
    return ["%s  [%s]  w=%s" % (t["text"], ", ".join(t.get("aliases", [])), t.get("weight"))
            for t in v.get("terms", [])]


def show_diff(label, before, after):
    d = list(difflib.unified_diff(before, after, "antes/" + label, "depois/" + label, lineterm="", n=0))
    print("\n".join(d) if d else "(%s: sem mudança)" % label)
    return bool(d)


# ---------- app control ----------
def app_running():
    return subprocess.run(["osascript", "-e", 'application id "%s" is running' % APP_ID],
                          capture_output=True, text=True).stdout.strip() == "true"


def quit_app():
    if E.get("FLUID_RESTART") == "0":
        return False
    if not app_running():
        return False
    subprocess.run(["osascript", "-e", 'tell application id "%s" to quit' % APP_ID], capture_output=True)
    for _ in range(40):
        if not app_running():
            break
        time.sleep(0.25)
    return True


def reopen_app(was_running):
    if E.get("FLUID_RESTART") == "0":
        print("(FLUID_RESTART=0: app não reiniciado)")
    elif was_running:
        subprocess.run(["open", "-b", APP_ID])
        print("FluidVoice reiniciado.")
    else:
        print("FluidVoice não estava aberto; não abri.")


# ---------- backup ----------
def make_backup(tag="backup"):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = "fluid-%s-%s.json" % (tag, datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    path = os.path.join(BACKUP_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"domain": DOMAIN, "entries": read_entries(), "vocabulary": read_vocab() if os.path.exists(VOCAB) else None},
                  f, ensure_ascii=False, indent=2)
    return path


# ---------- add (rule-order guard) ----------
def words(s):
    return s.lower().split()


def find_sub(hay, needle):
    n = len(needle)
    return [i for i in range(len(hay) - n + 1) if hay[i:i + n] == needle]


def rewrite(trigger, sub, repl):
    """Replace word-subsequence `sub` inside `trigger` by repl (lowercased), as the short rule would."""
    h, s = words(trigger), words(sub)
    for i in find_sub(h, s):
        return " ".join(h[:i] + words(repl) + h[i + len(s):])
    return None


def add_rule(entries, triggers, repl):
    triggers = [t.strip() for t in triggers if t.strip()]
    notes = []
    for e in entries:
        for t in triggers:
            if t.lower() in [x.lower() for x in e["triggers"]] and e["replacement"] != repl:
                die("o gatilho '%s' já existe com outra substituição ('%s'); remova ou edite antes" % (t, e["replacement"]))
    target = next((e for e in entries if e["replacement"] == repl), None)
    if target is None:
        target = {"triggers": [], "replacement": repl, "id": str(uuid.uuid4()).upper()}
        entries.append(target)
    have = {x.lower() for x in target["triggers"]}
    for t in triggers:
        if t.lower() not in have:
            target["triggers"].append(t)
            have.add(t.lower())
    # Guard: a short rule may fire before a longer one and break it.
    # (1) new short trigger inside an existing multiword trigger -> add the rewritten form to that rule.
    for e in list(entries):
        if e is target:
            continue
        for ex in list(e["triggers"]):
            if len(words(ex)) < 2:
                continue
            for t in triggers:
                if len(words(t)) < len(words(ex)):
                    v = rewrite(ex, t, repl)
                    if v and v not in [x.lower() for x in e["triggers"]]:
                        e["triggers"].append(v)
                        notes.append("'%s' contém '%s': somei '%s' à regra de '%s'" % (ex, t, v, e["replacement"]))
    # (2) an existing short rule inside the new multiword trigger -> add the rewritten form to the new rule.
    for t in list(triggers):
        if len(words(t)) < 2:
            continue
        for e in entries:
            if e is target:
                continue
            for ex in e["triggers"]:
                if len(words(ex)) < len(words(t)):
                    v = rewrite(t, ex, e["replacement"])
                    if v and v not in {x.lower() for x in target["triggers"]}:
                        target["triggers"].append(v)
                        notes.append("'%s' contém a regra '%s'->'%s': somei '%s'" % (t, ex, e["replacement"], v))
    return notes


def apply_change(new_entries=None, new_vocab=None, tag="auto"):
    path = make_backup(tag)
    print("backup: " + path)
    was = quit_app()
    if new_entries is not None:
        write_entries(new_entries)
    if new_vocab is not None:
        write_vocab(new_vocab)
    reopen_app(was)


def cmd_add(args):
    if "--" not in args:
        die("uso: add <gatilho...> -- <substituição>")
    i = args.index("--")
    triggers, repl = args[:i], " ".join(args[i + 1:]).strip()
    if not triggers or not repl:
        die("uso: add <gatilho...> -- <substituição>")
    before = read_entries()
    after = json.loads(json.dumps(before))
    for n in add_rule(after, triggers, repl):
        print("guarda de ordem: " + n)
    if not show_diff("dicionario", fmt_entries(before), fmt_entries(after)):
        return
    apply_change(new_entries=after, tag="add")


def cmd_boost(args):
    if not args:
        die("uso: boost <termo> [alias...]")
    term, aliases = args[0], args[1:]
    before = read_vocab()
    after = json.loads(json.dumps(before))
    t = next((x for x in after["terms"] if x["text"].lower() == term.lower()), None)
    if t is None:
        t = {"text": term, "aliases": [], "weight": WEIGHT}
        after["terms"].append(t)
    t["weight"] = WEIGHT
    for a in aliases:
        if a.lower() not in [x.lower() for x in t["aliases"]]:
            t["aliases"].append(a)
    if not show_diff("vocabulario", fmt_vocab(before), fmt_vocab(after)):
        return
    p = subprocess.run(["defaults", "read", DOMAIN, "VocabularyBoostingEnabled"], capture_output=True, text=True)
    if p.stdout.strip() != "1":
        print("aviso: VocabularyBoostingEnabled não é 1 em %s; o termo só vale com ele ligado." % DOMAIN)
    apply_change(new_vocab=after, tag="boost")


def cmd_list(_):
    print("# dicionário (%s)" % DOMAIN)
    print("\n".join(fmt_entries(read_entries())) or "(vazio)")
    print("# vocabulário (%s)" % VOCAB)
    print("\n".join(fmt_vocab(read_vocab())) or "(vazio)")


def cmd_backup(_):
    print(make_backup("backup"))


def cmd_restore(args):
    if len(args) != 1 or not os.path.isfile(args[0]):
        die("uso: restore <arquivo de backup>")
    b = json.load(open(args[0], encoding="utf-8"))
    make_path = make_backup("pre-restore")
    print("backup do estado atual: " + make_path)
    be, bv = read_entries(), read_vocab()
    show_diff("dicionario", fmt_entries(be), fmt_entries(b["entries"]))
    if b.get("vocabulary"):
        show_diff("vocabulario", fmt_vocab(bv), fmt_vocab(b["vocabulary"]))
    was = quit_app()
    write_entries(b["entries"])
    if b.get("vocabulary"):
        write_vocab(b["vocabulary"])
    reopen_app(was)


# ---------- scan ----------
def user_messages():
    """Yield (source, text) of user-authored messages. Read-only."""
    for f in glob.glob(CLAUDE_GLOB):
        try:
            for line in open(f, encoding="utf-8", errors="ignore"):
                if '"user"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                c = (o.get("message") or {}).get("content")
                if o.get("type") == "user" and isinstance(c, str) and not c.lstrip().startswith("<"):
                    yield "claude", c
        except OSError:
            pass
    dbs = E.get("FLUID_HERMES_DBS")
    dbs = dbs.split(":") if dbs else glob.glob(os.path.join(HOME, ".hermes/profiles/*/state.db")) + [os.path.join(HOME, ".hermes/state.db")]
    for db in dbs:
        if os.path.isfile(db):
            try:
                con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
                for (c,) in con.execute("select content from messages where role='user' and content is not null"):
                    yield "hermes", c
                con.close()
            except sqlite3.Error:
                pass


def history_rows():
    if not os.path.isfile(HISTORY):
        return
    try:
        con = sqlite3.connect("file:%s?mode=ro" % HISTORY, uri=True)
        for (p,) in con.execute("select payload from history"):
            try:
                o = json.loads(p)
                yield o.get("rawText") or "", o.get("processedText") or ""
            except Exception:
                pass
        con.close()
    except sqlite3.Error:
        pass


TOKEN = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9'’-]{2,}(?<!['’-])")

# Known dictation misspellings that are safe to suggest: (regex, source, replacement, why).
# Keep them generic (language-level), never names of a house.
PATTERNS = [
    (r"\bmara (o|a|os|as|ser)\b", "mara {1}", "para {1}", "'mara' antes de artigo/ser é 'para'; não troque 'Mara' sozinha (pode ser nome)"),
]

CORRECTION = re.compile(
    r"(?:n[ãa]o (?:é|e|se escreve|escreve)|not|no,? it'?s not)\s+[\"“'`]?([\w-]{3,})[\"”'`]?[,.;:]?\s+"
    r"(?:(?:mas|but|é|e|se escreve|it'?s|sim|\w+ é)\s+)+[\"“'`]?([\w-]{3,})[\"”'`]?", re.I)


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def plausible_fix(w, b):
    """True when b looks like what w was meant to be, not just an inflection of it."""
    a, c = fold(w), fold(b)
    if a == c or a.startswith(c) or c.startswith(a):  # accent/plural/gender/truncation
        return False
    if a[0] != c[0] or len(c) < 5 or abs(len(a) - len(c)) > 2:
        return False
    return True


def cmd_scan(args):
    top = 20
    if "--top" in args:
        top = int(args[args.index("--top") + 1])
    covered = {t.lower() for e in read_entries() for t in e["triggers"]}
    covered |= {a.lower() for t in read_vocab().get("terms", []) for a in t.get("aliases", [])}
    cand = collections.defaultdict(lambda: {"n": 0, "why": "", "kind": "", "ex": ""})

    def bump(src, dst, n, kind, why, ex=""):
        if src.lower() in covered or src.lower() == dst.lower():
            return
        c = cand[(src.lower(), dst)]
        c["n"] += n
        c["kind"], c["why"] = kind, why
        c["ex"] = c["ex"] or ex[:90]

    typed = collections.Counter()   # tokens in transcripts (user typed or dictated)
    dictated = collections.Counter()  # tokens in FluidVoice raw text
    corpus = []
    for _, text in user_messages():
        if len(text) > 1500 or text.lstrip().startswith("["):  # long pastes and system notices are not dictation
            continue
        corpus.append(text)
        typed.update(w.lower() for w in TOKEN.findall(text))
    for raw, proc in history_rows():
        corpus.append(raw)
        dictated.update(w.lower() for w in TOKEN.findall(raw))
        if raw and proc and raw.strip() != proc.strip():
            # FluidVoice's own raw->corrected pairs: token-level differences
            a, b = raw.split(), proc.split()
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
                if tag == "replace" and i2 - i1 <= 3 and j2 - j1 <= 3:
                    s, d = " ".join(a[i1:i2]).strip(".,;:!?"), " ".join(b[j1:j2]).strip(".,;:!?")
                    if len(s) > 2 and s.lower() != d.lower():
                        bump(s, d, 1, "histórico", "FluidVoice já corrigiu raw->texto final", raw)

    for text in corpus:
        for rx, src, dst, why in PATTERNS:
            for m in re.finditer(rx, text, re.I):
                g = m.group(1).lower()
                bump(src.format(None, g), dst.format(None, g), 1, "padrão", why, text)
        for m in CORRECTION.finditer(text):
            wrong, right = m.group(1), m.group(2)
            if wrong.lower() != right.lower() and len(text) < 400:
                bump(wrong, right, 3, "correção", "o usuário corrigiu: não é X, é Y", text)

    # near-miss: a token dictated often but rare in what the user types, close to a token typed often.
    stop = {t for t, _ in typed.most_common(300)}
    frequent = [t for t, c in typed.items() if c >= 4 and t not in stop and len(t) >= 4]
    for w, n in dictated.items():
        if n < 3 or w in stop or typed.get(w, 0) >= n or len(w) < 4:
            continue
        if typed.get(w, 0) > 2:
            continue
        best = [b for b in difflib.get_close_matches(w, frequent, n=5, cutoff=0.8) if plausible_fix(w, b) and dictated.get(b, 0) <= 1][:1]  # target never comes out of the ASR: a name or term it cannot spell
        if best and typed[best[0]] > typed.get(w, 0) * 2:
            bump(w, best[0], n, "parecido", "dita %dx; o texto digitado prefere '%s' (%dx)" % (n, best[0], typed[best[0]]))

    rows = sorted(cand.items(), key=lambda kv: -kv[1]["n"])[:top]
    print("# candidatos (nada foi aplicado)  fonte: %d mensagens, %d ditados" % (len(corpus), sum(1 for _ in history_rows())))
    for (src, dst), c in rows:
        print("%3d  %-9s %s -> %s  | %s" % (c["n"], c["kind"], src, dst, c["why"]))
        if c["ex"]:
            print("       ex: " + c["ex"])
    if not rows:
        print("(nenhum)")
    else:
        print("# aplicar: fix.sh add <gatilho> -- <substituição>  (e boost <termo> para nomes)")


def main():
    cmds = {"add": cmd_add, "boost": cmd_boost, "list": cmd_list, "backup": cmd_backup,
            "restore": cmd_restore, "scan": cmd_scan}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        die("uso: fix.sh add|boost|list|backup|restore|scan ...", 2)
    cmds[sys.argv[1]](sys.argv[2:])


main()
