#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Drive Hermes profiles from Claude Code or pi. Thin over the `hermes` CLI; stdlib only.

Exit codes: spawn/resume pass hermes -z's (0 ok, 1 no text, 2 partial/failed, 130 interrupted); 124 timeout;
3 profile busy (lock); 4 profile refused (per-token provider); 5 unknown profile; 6 WIP limit reached (spawn of
a code profile with --repo); 64 usage.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERMES = os.environ.get("HERMES_BIN", "hermes")
ROOT = Path(os.environ.get("HERMES_ROOT", "~/.hermes")).expanduser()
STATE = Path(os.environ.get("HERMES_SKILL_STATE", "~/.local/state/hermes-skill")).expanduser()

# Flat plans only: a per-token provider (openrouter, an Anthropic API key...) bills every call.
FLAT_PREFIXES = ("claude-subscription", "zai", "openai-codex")

# Task kind -> owning profile (references/routing.md is the human copy; keep both in step).
ROUTES = {
    "code": "hacker", "build": "hacker", "feature": "hacker", "fix": "hacker", "pr": "hacker",
    "research": "researcher",
    "ui": "hipster", "screen": "hipster", "widget": "hipster", "layout": "hipster", "css": "hipster",
    "swift": "hipster",
    "infra": "sre", "architecture": "sre", "hosting": "sre", "costs": "sre",
    "search": "via-ads", "ads": "via-ads", "seo": "via-ads",
    "disk": "mantainer", "mac": "mantainer", "upkeep": "mantainer",
    "coordination": "bili", "coordinate": "bili",
}
NO_ROUTE = "no owning profile: run it with a subagent of the session (backbrief step 9)"
EXIT_NOTE = {0: "ok", 1: "no text returned", 2: "partial or failed", 130: "interrupted", 124: "timeout"}


def die(msg, code):
    print(f"hermes.sh: {msg}", file=sys.stderr)
    sys.exit(code)


def home(profile):
    return ROOT if profile == "default" else ROOT / "profiles" / profile


def run_hermes(profile, *args, cwd=None, timeout=None):
    return subprocess.run([HERMES, "-p", profile, *args], capture_output=True, text=True, cwd=cwd, timeout=timeout)


def model_of(profile):
    """(model, provider) from the profile's config.yaml `model:` block only (never other keys, never secrets)."""
    out = {}
    try:
        lines = (home(profile) / "config.yaml").read_text().splitlines()
    except OSError:
        return "", ""
    inside = False
    for line in lines:
        if re.match(r"^model:\s*$", line):
            inside = True
        elif inside and re.match(r"^\s+(default|provider):", line):
            k, v = line.strip().split(":", 1)
            out[k] = v.strip().strip("'\"")
        elif inside and re.match(r"^\S", line):
            break
    return out.get("default", ""), out.get("provider", "")


def description(profile):
    try:
        lines = [x.strip() for x in (home(profile) / "SOUL.md").read_text().splitlines() if x.strip()]
    except OSError:
        return ""
    body = [x for x in lines if not x.startswith("#")]
    return (body or lines or [""])[0][:160]


def profiles():
    r = subprocess.run([HERMES, "profile", "list"], capture_output=True, text=True)
    if r.returncode != 0:
        die("`hermes profile list` failed", r.returncode)
    rows = []
    for line in r.stdout.splitlines():
        t = line.replace("◆", " ").split()
        if len(t) < 2 or set(line.strip()) <= set("─ ") or t[0] == "Profile":
            continue
        model, provider = model_of(t[0])
        rows.append({"profile": t[0], "model": t[1], "provider": provider, "description": description(t[0]),
                     "flat": provider.startswith(FLAT_PREFIXES) if provider else None})
    return rows


def require_flat(profile):
    names = [p["profile"] for p in profiles()]
    if profile not in names:
        die(f"unknown profile '{profile}' (known: {', '.join(names)})", 5)
    _, provider = model_of(profile)
    if not provider.startswith(FLAT_PREFIXES):
        die(f"profile '{profile}' uses provider '{provider or '?'}' (per-token or unknown); flat plans only: "
            + ", ".join(FLAT_PREFIXES), 4)


class Lock:
    """One writer per profile: mkdir is atomic; a dead pid's lock is taken over."""

    def __init__(self, profile):
        self.dir = STATE / "locks" / profile
        self.profile = profile

    def __enter__(self):
        self.dir.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                self.dir.mkdir()
                (self.dir / "pid").write_text(str(os.getpid()))
                return self
            except FileExistsError:
                try:
                    pid = int((self.dir / "pid").read_text())
                    os.kill(pid, 0)
                except (OSError, ValueError):
                    shutil.rmtree(self.dir, ignore_errors=True)  # stale
                    continue
                die(f"profile '{self.profile}' is busy (spawn running, pid {pid}); never two writers on one profile", 3)
        die(f"could not take the lock for '{self.profile}'", 3)

    def __exit__(self, *a):
        shutil.rmtree(self.dir, ignore_errors=True)


def warn_if_open_elsewhere(profile):
    """A profile open in a TUI/Desktop is a writer too; best effort, warns only."""
    try:
        ps = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True).stdout
    except OSError:
        return
    pat = re.compile(rf"hermes\S*\s+(--profile|-p)\s+{re.escape(profile)}\b")
    if any(pat.search(x) and " -z" not in x and " gateway" not in x for x in ps.splitlines()):
        print(f"hermes.sh: warning: '{profile}' looks open in a TUI; that is a second writer", file=sys.stderr)


def usage_of(path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not re.search(r"key|secret|token_value|auth", k, re.I)} if isinstance(data, dict) else {}


def execute(profile, extra, task, cwd, timeout):
    require_flat(profile)
    cwd = str(Path(cwd).expanduser()) if cwd else os.getcwd()
    if not Path(cwd).is_dir():
        die(f"--cwd {cwd} is not a directory", 64)
    with Lock(profile):
        warn_if_open_elsewhere(profile)
        fd, usage_file = tempfile.mkstemp(prefix="hermes-usage-", suffix=".json")
        os.close(fd)
        os.unlink(usage_file)
        t0 = time.time()
        try:
            r = run_hermes(profile, *extra, "-z", task, "--usage-file", usage_file, cwd=cwd, timeout=timeout)
            code, out, err = r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired as e:
            code, out, err = 124, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), ""
        usage = usage_of(usage_file)
        Path(usage_file).unlink(missing_ok=True)
    if out:
        print(out.rstrip("\n"))
    if code != 0:
        print(f"hermes.sh: exit {code} ({EXIT_NOTE.get(code, 'failed')}); not a success", file=sys.stderr)
        if err.strip():
            print(err.strip()[-500:], file=sys.stderr)
    sid = usage.get("session_id") or (extra[1] if extra[:1] == ["--resume"] else None)
    print(json.dumps({"profile": profile, "session_id": sid, "exit_code": code,
                      "duration_s": round(time.time() - t0, 1), "usage": usage}, ensure_ascii=False))
    sys.exit(code)


def cmd_list(a):
    rows = profiles()
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for p in rows:
        flag = "" if p["flat"] else "  [REFUSED: per-token or unknown provider]"
        print(f"{p['profile']:<12} {p['model']:<20} {p['description']}{flag}")


def wip_check(repo):
    """A code profile (the one `code` routes to) opens PRs: with --repo, `kanban.sh wip` must say there is room. Exit 3
    of kanban (at or over the limit) refuses the spawn; any other failure (no gh, no network) only warns."""
    kanban = Path(os.environ.get("HERMES_KANBAN") or Path(__file__).resolve().parents[2] / "kanban" / "scripts" / "kanban.sh")
    if not kanban.exists():
        print(f"hermes.sh: warning: {kanban} not found, WIP limit not checked", file=sys.stderr)
        return
    r = subprocess.run(["bash", str(kanban), "wip", "--repo", repo], capture_output=True, text=True)
    if r.returncode == 3:
        die(f"WIP limit reached, not spawning {ROUTES['code']}: finish or merge an open PR first.\n{r.stdout.strip()}", 6)
    if r.returncode != 0:
        print(f"hermes.sh: warning: WIP check failed ({r.stderr.strip() or r.returncode}), spawning anyway", file=sys.stderr)


def cmd_spawn(a):
    if a.repo and a.profile == ROUTES["code"]:
        wip_check(a.repo)
    execute(a.profile, [], a.task, a.cwd, a.timeout)


def cmd_resume(a):
    execute(a.profile, ["--resume", a.session], a.msg, a.cwd, a.timeout)


def cmd_sessions(a):
    require_flat(a.profile)
    r = run_hermes(a.profile, "sessions", "list", "--limit", str(a.limit))
    sys.stdout.write(r.stdout)
    sys.exit(r.returncode)


def cmd_read(a):
    require_flat(a.profile)
    with tempfile.TemporaryDirectory(prefix="hermes-export-") as d:
        r = run_hermes(a.profile, "sessions", "export", "--format", "md", "--session-id", a.session, d + "/")
        files = sorted(Path(d).rglob("*.md"))
        if r.returncode != 0 or not files:
            die(f"no export for session {a.session}: {r.stderr.strip()[-300:]}", r.returncode or 1)
        text = files[0].read_text()
    if len(text) > a.max_chars:
        text = text[: a.max_chars // 2] + f"\n\n[... {len(text) - a.max_chars} chars trimmed ...]\n\n" + text[-a.max_chars // 2:]
    print(text)


def cmd_dm(a):
    if not a.owner_asked:
        die("dm needs --owner-asked: only message a profile's bot when the owner asked for it", 64)
    r = subprocess.run([HERMES, "peer", "dm", a.target, a.msg], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr[-500:])
    sys.exit(r.returncode)


def cmd_memory(a):
    d = home(a.profile) / "memories"
    if not d.is_dir():
        die(f"no memories dir for '{a.profile}'", 5)
    for name in ("MEMORY.md", "USER.md"):
        f = d / name
        print(f"===== {name} =====")
        print(f.read_text() if f.exists() else "(missing)")


def cmd_route(a):
    kind = a.kind.strip().lower()
    if kind in ROUTES:
        print(ROUTES[kind])
        return
    die(f"'{a.kind}': {NO_ROUTE}", 1)


def main():
    p = argparse.ArgumentParser(prog="hermes.sh")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_list)
    s = sub.add_parser("spawn"); s.add_argument("profile"); s.add_argument("task")
    s.add_argument("--cwd"); s.add_argument("--timeout", type=int)
    s.add_argument("--repo", help="owner/name the work will open a PR on (code profile: refused at the WIP limit)")
    s.set_defaults(f=cmd_spawn)
    s = sub.add_parser("resume"); s.add_argument("profile"); s.add_argument("session"); s.add_argument("msg")
    s.add_argument("--cwd"); s.add_argument("--timeout", type=int); s.set_defaults(f=cmd_resume)
    s = sub.add_parser("sessions"); s.add_argument("profile"); s.add_argument("--limit", type=int, default=10)
    s.set_defaults(f=cmd_sessions)
    s = sub.add_parser("read"); s.add_argument("profile"); s.add_argument("session")
    s.add_argument("--max-chars", type=int, default=8000); s.set_defaults(f=cmd_read)
    s = sub.add_parser("dm"); s.add_argument("target"); s.add_argument("msg"); s.add_argument("--owner-asked", action="store_true")
    s.set_defaults(f=cmd_dm)
    s = sub.add_parser("memory"); s.add_argument("profile"); s.set_defaults(f=cmd_memory)
    s = sub.add_parser("route"); s.add_argument("kind", nargs="+"); s.set_defaults(f=cmd_route)
    a = p.parse_args()
    if a.cmd == "route":
        a.kind = " ".join(a.kind)
    a.f(a)


if __name__ == "__main__":
    main()
