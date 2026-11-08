#!/usr/bin/env python3
"""trace: the trace of why the last response was made, from the session transcript.

Reads ~/.claude/projects/<dir>/<session>.jsonl (read-only), finds the target turn and lists the resources
the owner authored that were in play: instruction files (CLAUDE.md, AGENTS.md), skills called, user files
read (wiki, SKILL.md, memory, settings) and hooks that injected context. `efeito` and `peso` are left
for the agent to fill (they are interpretation, so evidencia stays observed only for what the transcript shows).
"""
import argparse, glob, hashlib, json, os, re, sys, time

HOME = os.path.expanduser("~")
WIKI_HOME = os.path.normpath(os.path.expanduser(os.path.expandvars(os.environ.get("WIKI_HOME") or "~/wiki")))
PROJECTS = os.environ.get("BILIBOSS_PROJECTS", os.path.join(HOME, ".claude", "projects"))
NOT_OWNER_SKILLS = ("anthropic-skills:",)  # the owner's plugins are not listed here: everything else counts
OWNER_READ = re.compile(
    r"(/\.claude/|/\.wiki/|" + re.escape(WIKI_HOME) + r"/|/AGENTS\.md$|/CLAUDE\.md$|/SKILL\.md$|"
    r"/\.claude-plugin/|/memory/|/settings(\.local)?\.json$)"
)


def sessions(cwd_dir=None):
    pat = os.path.join(PROJECTS, cwd_dir or "*", "*.jsonl")
    return sorted(glob.glob(pat), key=os.path.getmtime)


def default_dir():
    return os.getcwd().replace("/", "-").replace(".", "-")


def load(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def user_text(rec):
    """The typed text of a user record, '' when it is only a tool_result or empty."""
    if rec.get("type") != "user" or rec.get("isMeta"):
        return ""
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, str):
        pass
    elif isinstance(c, list):
        c = "\n".join(b.get("text", "") for b in c if b.get("type") == "text")
    else:
        c = ""
    # Slash-command echoes (/model, ...) are not prompts the assistant answered.
    return "" if c.lstrip().startswith(("<local-command", "<command-name>")) else c


def split_turns(recs):
    """Turn = a typed user prompt up to the next one. Returns [(start_index, end_index, prompt)]."""
    starts = [i for i, r in enumerate(recs) if user_text(r).strip()]
    return [(s, (starts[k + 1] if k + 1 < len(starts) else len(recs)), user_text(recs[s]).strip())
            for k, s in enumerate(starts)]


def pick_turn(recs, back):
    turns = split_turns(recs)
    # The last prompt is usually this very skill being invoked: the target is the one before it.
    if turns and re.search(r"\btrace\b|por que|porque|why|o que você usou", turns[-1][2][:400], re.I) and len(turns) > 1:
        turns = turns[:-1]
    if len(turns) < back:
        sys.exit("trace: sessão sem turno anterior")
    return turns[-back]


def owner_path(p):
    return bool(p) and bool(OWNER_READ.search(p))


def kind_of(p):
    if p.endswith("AGENTS.md"):
        return "agents_md"
    if p.endswith("CLAUDE.md"):
        return "claude_md"
    if p.endswith("SKILL.md"):
        return "skill"
    if "/.wiki/" in p or p.startswith(WIKI_HOME + "/"):
        return "wiki"
    if "/memory/" in p:
        return "memoria"
    if "settings" in os.path.basename(p) or "/.claude-plugin/" in p:
        return "settings"
    return "arquivo"


def spans_for(recs, start, end):
    spans, seen = [], set()

    def add(**kw):
        key = (kw["tipo"], kw["caminho"], kw["entrada"])
        if key in seen:
            return
        seen.add(key)
        kw.setdefault("evidencia", "observed")
        kw.setdefault("efeito", "")
        kw.setdefault("peso", "")
        spans.append(kw)

    # Instruction files loaded by the session (ctx): the session-wide attachment, before the turn.
    for r in recs[:end]:
        a = r.get("attachment") or {}
        if a.get("type") == "instructions":
            for f in a.get("files") or []:
                p = f.get("path", "")
                add(tipo=kind_of(p), caminho=p, entrada="ctx", ordem=-1,
                    detalhe=(f.get("content") or "")[:0])
        if a.get("type") == "nested_memory" and a.get("path"):
            add(tipo=kind_of(a["path"]), caminho=a["path"], entrada="ctx", ordem=-1)

    for i in range(start, end):
        r = recs[i]
        a = r.get("attachment") or {}
        if a.get("type") in ("hook_additional_context", "hook_success"):
            body = a.get("content") or ""
            if isinstance(body, list):
                body = " ".join(map(str, body))
            if a.get("type") == "hook_additional_context" and body:
                add(tipo="hook", caminho=a.get("hookName", "hook"), entrada="ctx", ordem=i,
                    detalhe=body[:160])
            elif a.get("type") == "hook_success" and "additionalContext" in (a.get("stdout") or ""):
                add(tipo="hook", caminho=a.get("hookName", "hook"), entrada="ctx", ordem=i,
                    detalhe=(a.get("stdout") or "")[:160])
        m = r.get("message") or {}
        if r.get("type") == "assistant" and isinstance(m.get("content"), list):
            for b in m["content"]:
                if b.get("type") != "tool_use":
                    continue
                inp = b.get("input") or {}
                if b["name"] == "Skill":
                    name = inp.get("skill", "")
                    if not name.startswith(NOT_OWNER_SKILLS):
                        add(tipo="skill", caminho=name, entrada="skill", ordem=i)
                elif b["name"] in ("Read", "Edit", "Write"):
                    p = inp.get("file_path", "")
                    if owner_path(p):
                        add(tipo=kind_of(p), caminho=p, entrada=b["name"].lower(), ordem=i)
    return spans


def to_otlp(spans, session, prompt, t0):
    tid = hashlib.sha256(session.encode()).hexdigest()[:32]
    root = hashlib.sha256((session + prompt).encode()).hexdigest()[:16]
    ns = str(int(t0 * 1e9))

    def attr(k, v):
        return {"key": k, "value": {"stringValue": str(v)}}

    out = [{"traceId": tid, "spanId": root, "name": "resposta", "kind": 1,
            "startTimeUnixNano": ns, "endTimeUnixNano": ns,
            "attributes": [attr("trace.prompt", prompt[:200])]}]
    for n, s in enumerate(spans):
        out.append({"traceId": tid, "spanId": hashlib.sha256(f"{root}{n}".encode()).hexdigest()[:16],
                    "parentSpanId": root, "name": f"{s['tipo']}:{s['caminho']}", "kind": 1,
                    "startTimeUnixNano": ns, "endTimeUnixNano": ns,
                    "attributes": [attr(f"trace.{k}", v) for k, v in s.items() if k != "ordem"]})
    return {"resourceSpans": [{"resource": {"attributes": [attr("service.name", "trace")]},
                               "scopeSpans": [{"scope": {"name": "trace"}, "spans": out}]}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("session", nargs="?", help="transcript .jsonl (default: the newest of this folder)")
    ap.add_argument("--back", type=int, default=1, help="1 = last response, 2 = the one before")
    ap.add_argument("--otlp", metavar="FILE", help="also write OTLP/JSON to FILE")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the tree")
    a = ap.parse_args()

    path = a.session
    if not path:
        found = sessions(default_dir()) or sessions()
        if not found:
            sys.exit("trace: nenhum transcript em " + PROJECTS)
        path = found[-1]
    recs = load(path)
    start, end, prompt = pick_turn(recs, a.back)
    spans = spans_for(recs, start, end)
    sid = os.path.basename(path)[:-6]

    if a.otlp:
        with open(a.otlp, "w", encoding="utf-8") as fh:
            json.dump(to_otlp(spans, sid, prompt, time.time()), fh, ensure_ascii=False, indent=1)
    if a.json:
        print(json.dumps({"session": sid, "prompt": prompt[:200], "spans": spans}, ensure_ascii=False, indent=1))
        return
    print(f'trace  {sid[:8]}  "{prompt[:70].strip()}"')
    for n, s in enumerate(spans):
        last = n == len(spans) - 1
        print(f'{"└─" if last else "├─"} [{s["tipo"]}] {s["caminho"]}  ({s["entrada"]}, {s["evidencia"]})')
        if s.get("detalhe"):
            print(f'{"   " if last else "│  "}   · {s["detalhe"][:110]}')
    print(f"resumo: {len(spans)} recursos seus; efeito e peso: o agente preenche (inferred)")


if __name__ == "__main__":
    main()
