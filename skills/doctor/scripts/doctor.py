#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Generic doctor: is this repo healthy and ready to work in?

Read-only. Five dimensions: environment, architecture, behavior, observability, agent.
Each finding: {dimension, check, status ok|warn|drift|fail, evidence, action}.
The doctor never runs an `action`; it only prints it.

Exit: 0 healthy (ok/warn only), 1 drift or fail present, 2 the doctor could not run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:  # python 3.10
    tomllib = None  # type: ignore

STATUSES = ("ok", "warn", "drift", "fail")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target", ".mypy_cache", ".pytest_cache"}
NESTED_ENV = "DOCTOR_NESTED"


@dataclass
class Finding:
    dimension: str
    check: str
    status: str
    evidence: str
    action: str = ""

    def line(self) -> str:
        tail = f" -> {self.action}" if self.action else ""
        return f"{self.status} {self.dimension} {self.check}: {self.evidence}{tail}"


def run(cmd: list[str], cwd: Path, timeout: float) -> tuple[int | None, str]:
    """Run with a hard timeout (kills the process group). Returns (rc|None on timeout, output)."""
    env = {**os.environ, NESTED_ENV: "1", "GIT_TERMINAL_PROMPT": "0"}
    try:
        p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, start_new_session=True)
    except OSError as e:
        return 127, str(e)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out or ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = p.communicate()
        return None, out or ""


def tail(text: str, n: int = 200) -> str:
    text = " ".join(text.split())
    return text[-n:]


def read_toml(path: Path) -> dict:
    if tomllib is None or not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text())
    except Exception:
        return {}


def justfile_recipes(root: Path) -> list[str]:
    for name in ("justfile", "Justfile", ".justfile"):
        f = root / name
        if f.exists():
            return re.findall(r"^([A-Za-z_][\w-]*)\b[^:=\n]*:(?!=)", f.read_text(), re.M)
    return []


def package_json(root: Path) -> dict:
    f = root / "package.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {}


class Doctor:
    def __init__(self, root: Path, gate: bool, timeout: float, project_doctor: bool):
        self.root = root
        self.gate = gate
        self.timeout = timeout
        self.project_doctor = project_doctor
        self.findings: list[Finding] = []
        self.pyproject = read_toml(root / "pyproject.toml")
        self.pkg = package_json(root)
        self.recipes = justfile_recipes(root)

    def add(self, dim: str, check: str, status: str, evidence: str, action: str = "") -> None:
        self.findings.append(Finding(dim, check, status, evidence, action))

    def has(self, *names: str) -> bool:
        return any((self.root / n).exists() for n in names)

    # ---------------------------------------------------------------- environment
    def environment(self) -> None:
        d = "environment"
        stacks = []
        if self.has("pyproject.toml", "uv.lock", "requirements.txt"):
            stacks.append("python")
        if self.has("package.json"):
            stacks.append("node")
        if self.has("go.mod"):
            stacks.append("go")
        if self.recipes:
            stacks.append("just")
        if self.has("Dockerfile", "compose.yaml", "docker-compose.yml"):
            stacks.append("docker")
        if not stacks:
            self.add(d, "stack", "warn", "no known stack file (pyproject, package.json, go.mod, justfile, Dockerfile)",
                     "add the project's manifest or tell the doctor which stack it is")
        else:
            self.add(d, "stack", "ok", ", ".join(stacks))

        def tool(name: str, why: str, level: str = "fail") -> None:
            p = shutil.which(name)
            if p:
                self.add(d, f"tool:{name}", "ok", p)
            else:
                self.add(d, f"tool:{name}", level, f"{name} not on PATH ({why})", f"install {name} (e.g. brew install {name})")

        if "python" in stacks:
            tool("uv", "python project")
        if "node" in stacks:
            tool("node", "package.json")
            for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("package-lock.json", "npm")):
                if self.has(lock):
                    tool(pm, f"{lock} present")
                    break
            else:
                tool("npm", "package.json")
        if "go" in stacks:
            tool("go", "go.mod")
        if "just" in stacks:
            tool("just", "justfile")
        if "docker" in stacks:
            tool("docker", "Dockerfile", "warn")

        # dependencies installed / lock in sync
        if "python" in stacks:
            if self.has("uv.lock") and self.has("pyproject.toml"):
                if (self.root / "uv.lock").stat().st_mtime + 1 < (self.root / "pyproject.toml").stat().st_mtime:
                    self.add(d, "python-lock", "drift", "pyproject.toml is newer than uv.lock", "uv lock")
                else:
                    self.add(d, "python-lock", "ok", "uv.lock is not older than pyproject.toml")
            if self.has("pyproject.toml"):
                if self.has(".venv"):
                    self.add(d, "python-venv", "ok", ".venv present")
                else:
                    self.add(d, "python-venv", "warn", "no .venv", "uv sync")
        if "node" in stacks:
            if self.has("node_modules"):
                self.add(d, "node-modules", "ok", "node_modules present")
            else:
                self.add(d, "node-modules", "warn", "node_modules missing", "npm install (or the lockfile's package manager)")

        # git state
        if (self.root / ".git").exists():
            rc, out = run(["git", "status", "--porcelain"], self.root, 15)
            n = len([l for l in out.splitlines() if l.strip()]) if rc == 0 else -1
            if n == 0:
                self.add(d, "git-clean", "ok", "working tree clean")
            elif n > 0:
                self.add(d, "git-clean", "warn", f"{n} uncommitted path(s); someone else's work may be in the tree",
                         "work in a worktree (wt switch -c <task> --base origin/main --no-cd)")
        else:
            self.add(d, "git-repo", "warn", "not a git repository", "git init, or run the doctor at the repo root")

    # ---------------------------------------------------------------- architecture
    def architecture(self) -> None:
        d = "architecture"
        readme = next((n for n in ("README.md", "README", "README.rst") if self.has(n)), None)
        if readme:
            self.add(d, "readme", "ok", readme)
        else:
            self.add(d, "readme", "fail", "no README", "write README.md: what it is, how to run, how to verify")
        mem = [n for n in (".wiki", "docs", "doc") if (self.root / n).is_dir()]
        if mem:
            self.add(d, "wiki-or-docs", "ok", ", ".join(mem))
        else:
            self.add(d, "wiki-or-docs", "warn", "no .wiki/ or docs/", "create .wiki/ (wiki-smith) with the components and invariants")
        guides = [n for n in ("AGENTS.md", "CLAUDE.md") if self.has(n)]
        if guides:
            self.add(d, "agent-guide", "ok", ", ".join(guides))
        else:
            self.add(d, "agent-guide", "warn", "no AGENTS.md or CLAUDE.md", "write AGENTS.md: commands, layout, rules for agents")

        eps: list[str] = []
        scripts = (self.pyproject.get("project", {}) or {}).get("scripts", {})
        eps += [f"cli:{k}" for k in scripts]
        b = self.pkg.get("bin")
        if isinstance(b, dict):
            eps += [f"bin:{k}" for k in b]
        elif isinstance(b, str):
            eps.append(f"bin:{b}")
        if self.pkg.get("main"):
            eps.append(f"main:{self.pkg['main']}")
        for cand in ("main.py", "app.py", "__main__.py", "src/main.py", "main.go", "index.js", "src/index.ts"):
            if self.has(cand):
                eps.append(cand)
        cmd = self.root / "cmd"
        if cmd.is_dir():
            eps += [f"cmd/{p.name}" for p in sorted(cmd.iterdir()) if p.is_dir()]
        eps += [f"just:{r}" for r in self.recipes[:6]]
        sdir = self.root / "scripts"
        if sdir.is_dir():
            eps += [f"scripts/{p.name}" for p in sorted(sdir.iterdir()) if p.is_file()][:6]
        skills = self.root / "skills"
        if skills.is_dir():
            n = len([p for p in skills.iterdir() if (p / "SKILL.md").exists()])
            if n:
                eps.append(f"skills/*/SKILL.md x{n}")
        if eps:
            self.add(d, "entry-points", "ok", ", ".join(eps[:12]) + (" ..." if len(eps) > 12 else ""))
        else:
            self.add(d, "entry-points", "warn", "none found", "document the entry points in README or .wiki/")

    # ---------------------------------------------------------------- behavior
    def behavior(self) -> None:
        """Runs after the project doctor: behaviour is proven only by the project's own smokes and critical rules."""
        d = "behavior"
        verified = [f for f in self.findings if f.dimension == d and f.status == "ok"]
        if verified:
            self.add(d, "smoke", "ok", f"{len(verified)} verified finding(s) from the project doctor")
            return
        status = "fail" if self.gate else "warn"
        self.add(d, "smoke", status, "no verified `behavior` finding (ok) from a project doctor",
                 "add smokes and critical-rule checks to the project doctor, dimension behavior (see skill doctor)")

    # ---------------------------------------------------------------- observability
    def observability(self) -> None:
        d = "observability"
        pats = {
            "logging": re.compile(r"\b(import logging|structlog|slog\.|zerolog|winston|pino|console\.(log|error)|log\.(Print|Fatal|Info)|print\(f?[\"'].*(error|ERROR))"),
            "health": re.compile(r"/(health|healthz|readyz|livez|ready|ping)\b|def (health|doctor)\b"),
            "nats": re.compile(r"\bnats\b", re.I),
        }
        found: dict[str, str] = {}
        seen = 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
            for fn in filenames:
                if not fn.endswith((".py", ".js", ".ts", ".go", ".sh", ".md", ".toml", ".yaml", ".yml", ".json")):
                    continue
                seen += 1
                if seen > 600:
                    break
                p = Path(dirpath) / fn
                try:
                    if p.stat().st_size > 200_000:
                        continue
                    text = p.read_text(errors="ignore")
                except OSError:
                    continue
                for k, rx in pats.items():
                    if k not in found and rx.search(text):
                        found[k] = str(p.relative_to(self.root))
            if seen > 600:
                break
        if "logging" in found:
            self.add(d, "logging", "ok", f"found in {found['logging']}")
        else:
            self.add(d, "logging", "warn", "no logging calls found", "log errors and key events (stderr or a JSONL under ~/.local/state)")
        if "health" in found:
            self.add(d, "health", "ok", f"health/doctor hook in {found['health']}")
        else:
            self.add(d, "health", "warn", "no health endpoint or doctor method found", "add `doctor` (see skill doctor) or a /health endpoint")
        if "nats" in found:
            self.add(d, "events", "ok", f"NATS mentioned in {found['nats']}")
        else:
            self.add(d, "events", "ok", "no NATS usage (not required)")

    # ---------------------------------------------------------------- agent
    def agent(self) -> None:
        d = "agent"
        for t in ("git", "gh", "gh-app"):
            p = shutil.which(t)
            if p:
                self.add(d, f"cli:{t}", "ok", p)
            elif t == "gh-app":
                self.add(d, f"cli:{t}", "warn", "gh-app not on PATH (house commits and PRs go through it)", "install/link gh-app into ~/.local/bin")
            else:
                self.add(d, f"cli:{t}", "fail" if t == "git" else "warn", f"{t} not on PATH", f"brew install {t}")
        if shutil.which("gh"):
            rc, out = run(["gh", "auth", "status"], self.root, 15)
            if rc == 0:
                self.add(d, "gh-auth", "ok", "gh authenticated")
            else:
                self.add(d, "gh-auth", "warn", f"gh auth status: {tail(out, 120) or 'timed out'}", "gh auth login (the owner does the login)")
        if (self.root / ".git").exists():
            rc, out = run(["git", "remote", "get-url", "origin"], self.root, 10)
            if rc != 0:
                self.add(d, "git-remote", "warn", "no origin remote", "git remote add origin <url>")
            else:
                url = out.strip()
                rc, out = run(["git", "ls-remote", "--exit-code", "-h", "origin", "HEAD"], self.root, 15)
                if rc == 0 or rc == 2:  # 2 = reachable, no matching ref
                    self.add(d, "git-remote", "ok", f"origin reachable ({url})")
                elif rc is None:
                    self.add(d, "git-remote", "warn", f"git ls-remote timed out ({url})", "check network/VPN/credentials")
                else:
                    self.add(d, "git-remote", "fail", f"git ls-remote exit {rc}: {tail(out, 120)}", "check the remote URL and credentials")
        if os.access(self.root, os.W_OK):
            self.add(d, "write-permission", "ok", f"{self.root} is writable")
        else:
            self.add(d, "write-permission", "fail", f"{self.root} is not writable", "fix permissions or work in a worktree you own")
        self.secrets_presence()

    def secrets_presence(self) -> None:
        """Names only. Never reads or prints a value."""
        d = "agent"
        for ex in (".env.example", "casa.env.example", ".env.sample"):
            f = self.root / ex
            if not f.exists():
                continue
            keys = re.findall(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=", f.read_text(), re.M)
            real = self.root / ".env"
            real_keys = set(re.findall(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=", real.read_text(), re.M)) if real.exists() else set()
            missing = [k for k in keys if k not in os.environ and k not in real_keys]
            if not keys:
                continue
            if missing:
                self.add(d, f"env:{ex}", "warn", f"{len(missing)}/{len(keys)} variable(s) not set: {', '.join(missing[:6])}",
                         "set them through envless (never paste values in chat)")
            else:
                self.add(d, f"env:{ex}", "ok", f"all {len(keys)} variable(s) present (names only checked)")
            break

    # ---------------------------------------------------------------- project doctor
    def discover_project_doctor(self) -> list[tuple[str, list[str], bool]]:
        found: list[tuple[str, list[str], bool]] = []
        if "doctor" in self.recipes and shutil.which("just"):
            found.append(("just doctor", ["just", "doctor"], False))
        sdir = self.root / "scripts"
        if sdir.is_dir():
            for p in sorted(sdir.glob("doctor*")):
                if p.is_file() and os.access(p, os.X_OK) and p.resolve() != Path(__file__).resolve():
                    found.append((f"scripts/{p.name}", [str(p), "--json"], True))
        clis = list(((self.pyproject.get("project", {}) or {}).get("scripts", {})).keys())
        b = self.pkg.get("bin")
        if isinstance(b, dict):
            clis += list(b)
        for c in clis:
            if shutil.which(c):
                found.append((f"{c} doctor", [c, "doctor", "--json"], True))
        return found

    def run_project_doctor(self, cmd: list[str]) -> tuple[int | None, str, bool]:
        """Asks for the ok findings with --verbose; a doctor that refuses the flag runs again without it."""
        rc, out = run([*cmd, "--verbose"], self.root, self.timeout)
        if rc is None or not (rc == 2 or (rc != 0 and not parse_findings(out))):
            return rc, out, True
        rc, out = run(cmd, self.root, self.timeout)
        return rc, out, False

    def merge_project_doctor(self) -> None:
        if not self.project_doctor or os.environ.get(NESTED_ENV):
            return
        found = self.discover_project_doctor()
        if not found:
            self.add("architecture", "project-doctor", "warn", "no project doctor found (just doctor, scripts/doctor*, <cli> doctor)",
                     "propose one: `just doctor` recipe or scripts/doctor (see skill doctor)")
            return
        for label, cmd, _json in found:
            rc, out, verbose = self.run_project_doctor(cmd)
            got = parse_findings(out)
            how = "" if verbose else " (without --verbose: it refused the flag)"
            self.add("architecture", "project-doctor", "ok", f"`{label}` ran, {len(got)} finding(s) merged{how}")
            for f in got:
                f.check = f"{label}:{f.check}"
                self.findings.append(f)
            if rc is None:
                self.add("architecture", "project-doctor", "fail", f"`{label}` timed out", f"run `{label}` by hand")
            elif not got and rc != 0:
                self.add("architecture", "project-doctor", "fail", f"`{label}` exit {rc}, output not parseable: {tail(out)}",
                         f"run `{label}` by hand; make it print `<status> <dimension> <check>: <evidence> -> <action>`")

    def all(self) -> list[Finding]:
        self.environment()
        self.architecture()
        self.observability()
        self.agent()
        self.merge_project_doctor()
        self.behavior()
        return self.findings


LINE_RX = re.compile(r"^(ok|warn|drift|fail)\s+(\S+)\s+(\S+?):\s*(.*?)(?:\s+->\s+(.*))?$")


def parse_findings(out: str) -> list[Finding]:
    got = []
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                o = json.loads(ln)
                if o.get("status") in STATUSES and o.get("dimension") and o.get("check"):
                    got.append(Finding(o["dimension"], str(o["check"]), o["status"], str(o.get("evidence", "")), str(o.get("action", ""))))
            except json.JSONDecodeError:
                pass
            continue
        m = LINE_RX.match(ln)
        if m:
            got.append(Finding(m[2], m[3], m[1], m[4], m[5] or ""))
    return got


def main() -> int:
    ap = argparse.ArgumentParser(description="Generic doctor: is this repo healthy and ready to work in?")
    ap.add_argument("path", nargs="?", default=".", help="repo directory (default .)")
    ap.add_argument("--json", action="store_true", help="one JSON object per finding")
    ap.add_argument("--verbose", action="store_true", help="also print ok findings")
    ap.add_argument("--gate", action="store_true", help="no verified behavior finding from a project doctor is a fail")
    ap.add_argument("--timeout", type=float, default=120, help="seconds for each project doctor (default 120)")
    ap.add_argument("--no-project-doctor", action="store_true", help="skip discovery of the project's own doctor")
    a = ap.parse_args()

    root = Path(a.path).expanduser().resolve()
    if not root.is_dir():
        print(f"doctor: not a directory: {root}", file=sys.stderr)
        return 2
    try:
        findings = Doctor(root, a.gate, a.timeout, not a.no_project_doctor).all()
    except Exception as e:  # the doctor itself broke
        print(f"doctor: could not run: {e}", file=sys.stderr)
        return 2

    counts = {s: sum(1 for f in findings if f.status == s) for s in STATUSES}
    shown = [f for f in findings if a.verbose or f.status != "ok"]
    for f in shown:
        print(json.dumps(asdict(f), ensure_ascii=False) if a.json else f.line())
    summary = f"summary {root.name}: {counts['ok']} ok, {counts['warn']} warn, {counts['drift']} drift, {counts['fail']} fail"
    print(summary, file=sys.stderr if a.json else sys.stdout)
    return 1 if counts["drift"] or counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
