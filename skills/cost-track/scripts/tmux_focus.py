# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""The cost clock follows the tmux session the owner is attached to (the only writer of the clock).

    costs.sh tmux-focus <session-name|->   attach / switch / detach (hooks call this); silent, idempotent, exit 0
    costs.sh tmux-install                  hooks in ~/.tmux.conf (marked block) and live in the running tmux
    costs.sh tmux-uninstall                the opposite
    costs.sh status                        the running entry, one line
    costs.sh simulate <session|->          exactly what the hook runs, with no tmux switch (logged source=simulate)
    costs.sh trace [n]                     the last n lines of ~/.local/state/clock.log (bash, no uv)
    costs.sh check [session|--tmux]        running.json vs the owner's session; exit 0 if consistent (bash, no uv)

A session named like an open Kanban card (Upstream or Downstream; the slug of its title, or its domain) runs the
clock in that card's domain, counting for the domain's cost center. Any other session, or '-' (detach), stops it.
Stdlib only; reads the Kanban journal (KANBAN_DIR) and writes the Costs journal (COSTS_DIR) through costs.py.
"""
from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEGIN, END = "# >>> cost-track tmux-focus >>>", "# <<< cost-track tmux-focus <<<"
HOOKS = {"client-session-changed": "#{session_name}", "client-attached": "#{session_name}", "client-detached": "-"}
HOOK_INDEX = 90  # an indexed hook never clobbers the owner's own set-hook
OPEN_STAGES = ("Upstream", "Downstream")
ACTOR = "tmux-focus"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # a dataclass module needs itself registered
    spec.loader.exec_module(mod)
    return mod


C = _load("tf_costs", HERE / "costs.py")


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def open_card(session: str):
    """The open card a session name stands for (slug of its title first, then its domain), or None."""
    path = HERE.parent.parent / "kanban" / "scripts" / "kanban.py"
    if not path.exists() or not session:
        return None
    try:
        K = _load("tf_kanban", path)
        cards = [c for c in K.cards_from(K.events()) if str(c.stage) in OPEN_STAGES]
    except Exception:  # noqa: BLE001 - a broken neighbour must not break the clock
        return None
    want = slug(session)
    for pick in (lambda c: slug(c.title) == want, lambda c: slug(c.domain) == want):
        hit = sorted((c for c in cards if pick(c)), key=lambda c: c.since, reverse=True)
        if hit:
            return hit[0]
    return None


def declared_center(domain: str) -> str | None:
    """COST_CENTER of the domain's dev_console_project.py (read as text, never executed), else the journal's mapping."""
    lst = Path(os.environ.get("DEVC_DOMAINS", "~/.local/state/dev-console/domains.txt")).expanduser()
    try:
        files = [Path(p.strip()).expanduser() for p in lst.read_text().splitlines() if p.strip() and not p.startswith("#")]
    except OSError:
        files = []
    for f in files:
        try:
            src = f.read_text()
        except OSError:
            continue
        s = re.search(r'^SLUG\s*=\s*["\']([^"\']+)["\']', src, re.M)
        if s and s.group(1) == domain:
            m = re.search(r'^COST_CENTER\s*=\s*["\']([^"\']+)["\']', src, re.M)
            return C.center_of(domain, m.group(1) if m else None)
    return C.center_of(domain)


def stop(ended_by: str = "tmux") -> bool:
    run = C.running()
    if not run:
        return False
    started = datetime.fromisoformat(run["started_at"])
    seconds = max(round((C._now() - started).total_seconds()), 0)
    cost = round(seconds * run["rate_hour"] / 3600, 2)
    value = {"text": C.stopped_text(run["center"], run["domain"], seconds, cost), "domain": run["domain"], "seconds": seconds,
             "rate_hour": run["rate_hour"], "cost": cost, "ended_by": ended_by}
    if run.get("card"):
        value["card"] = run["card"]
    C.emit("time_entry.stopped", value, cost_center=run["center"], actor=ACTOR)
    C.set_running(None)
    return True


def start(card, session: str = "") -> bool:
    center = declared_center(card.domain)
    rate = C.rate_hour(center) if center else None
    if not rate:
        return False
    now = C._now().isoformat(timespec="seconds")
    C.emit("time_entry.started", {"text": C.started_text(center, card.domain), "domain": card.domain, "card": card.id},
           cost_center=center, actor=ACTOR)
    C.set_running({"center": center, "domain": card.domain, "card": card.id, "started_at": now, "last_seen": now,
                   "rate_hour": rate, "driver": "tmux", "session": session})
    return True


def focus(session: str) -> None:
    """Under a lock: two hooks firing together (attached + session-changed) must not both start an entry."""
    C.costs_dir().mkdir(parents=True, exist_ok=True)
    with (C.costs_dir() / "focus.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _focus(session)


def _focus(session: str) -> None:
    card = open_card(session) if session and session != "-" else None
    run = C.running()
    who = {"session": session, "card": card.id if card else None, "domain": card.domain if card else None}
    if card and run and run.get("card") == card.id and run.get("domain") == card.domain:
        C.clog("decision", **who, action="noop", reason="already running for this card", running=True)
        return  # already the running entry
    stopped = stop()
    started = start(card, session) if card else False
    action = "start" if started else "stop" if stopped else "noop"
    reason = ("session is an open card" if started else "card has no cost center" if card else
              "detached" if session in ("", "-") else "session is not an open card")
    C.clog("decision", **who, action=action, reason=reason, running=started)


def status() -> str:
    run = C.running()
    if not run:
        return "parado"
    return f"rodando: domínio {run['domain']} · centro {run['center']} · card {run.get('card', '-')} · desde {run['started_at']}"


# --- tmux hooks -------------------------------------------------------------------------------------------------
def _tmux(*args: str) -> bool:
    try:
        return subprocess.run([os.environ.get("TMUX_BIN", "tmux"), *args], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _cmd(sh: str, arg: str) -> str:
    return f"run-shell -b '{sh} tmux-focus {arg}'"


def install(sh: str, conf: Path) -> None:
    block = [BEGIN] + [f"set-hook -g {h}[{HOOK_INDEX}] \"{_cmd(sh, a)}\"" for h, a in HOOKS.items()] + [END]
    text = conf.read_text() if conf.exists() else ""
    text = _strip(text)
    conf.write_text(text + ("\n" if text and not text.endswith("\n\n") else "") + "\n".join(block) + "\n")
    for h, a in HOOKS.items():
        _tmux("set-hook", "-g", f"{h}[{HOOK_INDEX}]", _cmd(sh, a))


def _strip(text: str) -> str:
    return re.sub(rf"\n?{re.escape(BEGIN)}.*?{re.escape(END)}\n?", "\n", text, flags=re.S).lstrip("\n") if BEGIN in text else text


def uninstall(conf: Path) -> None:
    if conf.exists():
        conf.write_text(_strip(conf.read_text()))
    for h in HOOKS:
        _tmux("set-hook", "-gu", f"{h}[{HOOK_INDEX}]")


def main(argv: list[str]) -> int:
    cmd, rest = (argv[0], argv[1:]) if argv else ("", [])
    conf = Path(os.environ.get("TMUX_CONF", "~/.tmux.conf")).expanduser()
    sh = os.environ.get("COSTS_SH") or str(HERE / "costs.sh")
    if cmd == "tmux-focus":
        C.clog("hook", session=rest[0] if rest else "-", source=os.environ.get("CLOCK_SOURCE", "tmux"))
        try:
            focus(rest[0] if rest else "-")
        except Exception as err:  # noqa: BLE001 - a hook never fails; the message carries no values
            print(f"costs tmux-focus: {type(err).__name__}", file=sys.stderr)
        return 0
    if cmd == "tmux-install":
        install(sh, conf)
        print(f"hooks in {conf} and live ({', '.join(HOOKS)})")
        return 0
    if cmd == "tmux-uninstall":
        uninstall(conf)
        print("hooks removed")
        return 0
    if cmd == "status":
        print(status())
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
