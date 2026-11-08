#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6,<7", "jsonschema>=4,<5"]
# ///
"""Capability doctor. The generic doctor.py retains its original interface."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.parse

import yaml
import jsonschema

EXECUTORS = {"file", "grep", "schema", "cli", "http", "run", "sql", "browser", "agent"}
KINDS = {"fast", "runtime", "journey"}

class Invalid(ValueError):
    pass

class UniqueLoader(yaml.SafeLoader):
    pass

def unique_mapping(loader, node, deep=False):
    out = {}
    for key, value in node.value:
        k = loader.construct_object(key, deep=deep)
        if k in out:
            raise Invalid(f"duplicate YAML key: {k}")
        out[k] = loader.construct_object(value, deep=deep)
    return out

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

def require(condition, message):
    if not condition:
        raise Invalid(message)

def local(base, name):
    require(isinstance(name, str) and name, "path must be a nonempty string")
    p = (base / name).resolve()
    require(p.is_relative_to(base.resolve()), f"path escapes contract directory: {name}")
    return p

def argv(value):
    require(isinstance(value, list) and value and all(isinstance(x, str) and x for x in value), "command must be a nonempty argv list")

def read_contract(path):
    try:
        data = yaml.load(path.read_text(), Loader=UniqueLoader)
        require(isinstance(data, dict), "contract must be a mapping")
        require(set(data) <= {"capabilities", "doctor"}, "unknown contract field")
        caps = data.get("capabilities")
        require(isinstance(caps, dict) and caps, "capabilities must be a nonempty mapping")
        config = data.get("doctor", {})
        require(isinstance(config, dict), "doctor must be a mapping")
        require(set(config) <= {"timeout", "allowed_hosts", "adapters"}, "unknown doctor option")
        require(isinstance(config.get("timeout", 30), (int, float)) and 0 < config.get("timeout", 30) <= 3600, "invalid doctor timeout")
        require(isinstance(config.get("allowed_hosts", []), list) and all(isinstance(x, str) for x in config.get("allowed_hosts", [])), "allowed_hosts must be a list")
        adapters = config.get("adapters", {})
        require(isinstance(adapters, dict) and set(adapters) <= {"sql", "browser", "agent"}, "invalid adapters")
        for a in adapters.values():
            argv(a)
        ids = set()
        for name, cap in caps.items():
            require(isinstance(name, str) and isinstance(cap, dict), "invalid capability")
            require(set(cap) <= {"intent", "checks", "keep", "success"}, f"unknown field in capability {name}")
            require(isinstance(cap.get("intent"), str) and cap["intent"].strip(), f"{name}: intent required")
            checks = cap.get("checks")
            require(isinstance(checks, list) and checks, f"{name}: checks required")
            for c in checks:
                require(isinstance(c, dict), "check must be a mapping")
                require(set(c) <= EXECUTORS | {"id", "kind", "expected", "red", "remedy", "category", "timeout", "scripts"}, "unknown check field")
                for key in ("id", "expected", "red", "remedy"):
                    require(isinstance(c.get(key), str) and c[key].strip(), f"check needs {key}")
                require(re.fullmatch(r"[a-zA-Z0-9_.-]+", c["id"]) is not None, "invalid check id")
                require(c["id"] not in ids, f"duplicate check id: {c['id']}")
                ids.add(c["id"])
                require(c.get("kind") in KINDS, f"{c['id']}: explicit kind required")
                require(len(EXECUTORS & c.keys()) == 1, f"{c['id']}: exactly one executor required")
                require(isinstance(c.get("timeout", 30), (int, float)) and 0 < c.get("timeout", 30) <= 3600, "invalid timeout")
                require(isinstance(c.get("scripts", []), list), "scripts must be a list")
                for script in c.get("scripts", []):
                    require(local(path.parent, script).is_file(), f"referenced script absent: {script}")
                kind = next(iter(EXECUTORS & c.keys()))
                v = c[kind]
                if kind == "file":
                    local(path.parent, v)
                else:
                    require(isinstance(v, dict), f"{kind} must be a mapping")
                    allowed = {"grep": {"path", "pattern"}, "schema": {"path", "schema"}, "cli": {"command"}, "run": {"command", "why_script"}, "http": {"url", "status"}, "sql": {"query", "read_only"}, "browser": {"url", "test_environment"}, "agent": {"task"}}[kind]
                    require(set(v) <= allowed, f"unknown {kind} option")
                    if kind in {"cli", "run"}:
                        argv(v.get("command"))
                    if kind == "run":
                        require(isinstance(v.get("why_script"), str) and v["why_script"].strip(), "run requires why_script")
                    if kind in {"grep", "schema"}:
                        local(path.parent, v.get("path"))
                    if kind == "grep":
                        require(isinstance(v.get("pattern"), str), "grep requires pattern")
                        re.compile(v["pattern"])
                    if kind == "schema":
                        require(isinstance(v.get("schema"), dict), "schema requires inline JSON Schema")
                        jsonschema.Draft202012Validator.check_schema(v["schema"])
                    if kind in {"http", "browser"}:
                        u = urllib.parse.urlparse(v.get("url", ""))
                        require(u.scheme in {"http", "https"} and u.hostname and not u.username, "invalid URL")
                        if kind == "http":
                            require(u.hostname in config.get("allowed_hosts", []), "HTTP host not allowed")
                            require(isinstance(v.get("status", 200), int), "invalid HTTP status")
                        else:
                            require(v.get("test_environment") is True, "browser requires test_environment: true")
                    if kind == "sql":
                        require(v.get("read_only") is True and isinstance(v.get("query"), str), "SQL requires read_only and query")
                    if kind == "agent":
                        require(isinstance(v.get("task"), str) and v["task"].strip(), "agent requires task")
            own = {c["id"] for c in checks}
            keep = cap.get("keep", [])
            require(isinstance(keep, list) and all(isinstance(x, str) and x in own for x in keep), "invalid keep reference")
            success = cap.get("success")
            require(isinstance(success, list) and success, f"{name}: success must be a nonempty reference list")
            require(all(isinstance(x, str) and (x in own or x == "keep") for x in success), "invalid success reference")
        return data
    except (OSError, yaml.YAMLError, ValueError, TypeError, re.error, jsonschema.SchemaError) as e:
        raise Invalid(f"{path}: {e}") from e

def digest(path, c, config=None):
    config = config or {}
    h = hashlib.sha256(json.dumps({"check": c, "doctor": config}, sort_keys=True).encode())
    refs = set(c.get("scripts", []))
    for k in ("run", "cli"):
        if k in c:
            for a in c[k]["command"]:
                p = path.parent / a
                if p.is_file() and p.resolve().is_relative_to(path.parent.resolve()):
                    refs.add(a)
    for command in config.get("adapters", {}).values():
        for a in command:
            p = path.parent / a
            if p.is_file() and p.resolve().is_relative_to(path.parent.resolve()):
                refs.add(a)
    for r in sorted(refs):
        p = local(path.parent, r)
        h.update(r.encode())
        h.update(p.read_bytes())
    return h.hexdigest()

def state_dir(root, override):
    base = Path(override) if override else Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "doctor"
    base = base.expanduser().resolve()
    require(not base.is_relative_to(root), "evidence state must be outside the repository")
    return base / hashlib.sha256(str(root).encode()).hexdigest()[:24]

def proof_path(state, rel, c):
    return state / (hashlib.sha256(f"{rel}:{c['id']}".encode()).hexdigest() + ".json")

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def command_run(cmd, cwd, timeout, payload=None):
    p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE if payload else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = p.communicate(json.dumps(payload) if payload else None, timeout=timeout)
        infra = p.returncode in {2, 126, 127} or bool(re.search(r"can.t open file|SyntaxError:|ModuleNotFoundError:|command not found|No such file or directory", err))
        return p.returncode == 0, f"exit={p.returncode}\n{out}{err}".strip(), "infrastructure" if infra else "assertion"
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return False, f"timeout after {timeout}s", "timeout"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def execute(path, c, config):
    k = next(iter(EXECUTORS & c.keys()))
    v = c[k]
    timeout = c.get("timeout", config.get("timeout", 30))
    try:
        if k == "file":
            p = local(path.parent, v)
            return p.exists(), f"{v}: {'exists' if p.exists() else 'absent'}", "assertion"
        if k == "grep":
            p = local(path.parent, v["path"])
            if not p.is_file():
                return False, f"input file absent: {v['path']}", "infrastructure"
            match = re.search(v["pattern"], p.read_text())
            return bool(match), f"{v['path']}: pattern {'found' if match else 'absent'}", "assertion"
        if k == "schema":
            p = local(path.parent, v["path"])
            data = json.loads(p.read_text())
            errors = list(jsonschema.Draft202012Validator(v["schema"]).iter_errors(data))
            return not errors, "valid" if not errors else "; ".join(e.message for e in errors), "assertion"
        if k in {"cli", "run"}:
            return command_run(v["command"], path.parent, timeout)
        if k == "http":
            try:
                with urllib.request.build_opener(NoRedirect).open(v["url"], timeout=timeout) as response:
                    status = response.status
            except urllib.error.HTTPError as e:
                status = e.code
            return status == v.get("status", 200), f"HTTP {status}", "assertion"
        adapter = config.get("adapters", {}).get(k)
        if not adapter:
            return False, f"{k} adapter not configured", "pending"
        payload = {"executor": k, "definition": v}
        if k == "sql":
            payload["transaction"] = {"begin": "BEGIN TRANSACTION READ ONLY", "end": "ROLLBACK"}
        return command_run(adapter, path.parent, timeout, payload)
    except TimeoutError as e:
        return False, str(e), "timeout"
    except urllib.error.URLError as e:
        return False, str(e), "timeout" if isinstance(e.reason, TimeoutError) else "infrastructure"
    except (OSError, ValueError) as e:
        return False, str(e), "infrastructure"

def changed_files(root, base):
    def git(*args):
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
        require(p.returncode == 0, p.stderr.decode(errors="replace"))
        return p.stdout
    files = set()
    diffs = [git("diff", "--find-renames", "--name-status", "-z", "HEAD"), git("diff", "--cached", "--find-renames", "--name-status", "-z")]
    if base:
        git("rev-parse", "--verify", f"{base}^{{commit}}")
        diffs.append(git("diff", "--find-renames", "--name-status", "-z", f"{base}...HEAD"))
    for diff in diffs:
        tokens = iter(diff.decode().strip("\0").split("\0"))
        for status in tokens:
            if not status:
                continue
            files.add(next(tokens))
            if status.startswith(("R", "C")):
                files.add(next(tokens))
    files.update(x for x in git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0") if x)
    return sorted(files)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="*")
    p.add_argument("--root", default=".")
    p.add_argument("--all", action="store_true")
    p.add_argument("--capability", action="append", default=[])
    p.add_argument("--changed", action="store_true")
    p.add_argument("--base")
    p.add_argument("--json", action="store_true")
    p.add_argument("--state-dir")
    p.add_argument("--record-red", metavar="CHECK")
    p.add_argument("--confirm-red", help="Exact declared red reason, after reviewing the observed failure")
    p.add_argument("--confirm-observed", help="SHA256 of the observed output being confirmed")
    args = p.parse_args()
    try:
        root = Path(args.root).resolve()
        mode = "fast"
        if args.paths and args.paths[0] in {"runtime", "journey"}:
            mode = args.paths.pop(0)
        require(not args.base or args.changed, "--base requires --changed")
        require(not args.confirm_red or args.record_red, "--confirm-red requires --record-red")
        require(not args.confirm_observed or args.confirm_red, "--confirm-observed requires --confirm-red")
        paths = sorted(x for x in root.rglob(".doctor.yaml") if not any(y in {".git", "node_modules", ".venv"} for y in x.relative_to(root).parts))
        require(paths, "no .doctor.yaml contracts found")
        # Validate every discovered contract before any command, including unselected contracts.
        contracts = {x: read_contract(x) for x in paths}
        state = state_dir(root, args.state_dir)
        uncovered = []
        if args.changed:
            selected = set()
            for f in changed_files(root, args.base):
                matches = [x for x in paths if (root / f).is_relative_to(x.parent)]
                if matches:
                    selected.add(max(matches, key=lambda x: len(x.parts)))
                else:
                    uncovered.append(f)
        else:
            selected = set(paths)
            if args.paths:
                selected = set()
                for a in args.paths:
                    target = (root / a).resolve()
                    require(target.is_relative_to(root), "selection outside root")
                    descendants = [x for x in paths if x == target or x.is_relative_to(target)]
                    if descendants:
                        selected.update(descendants)
                    else:
                        ancestors = [x for x in paths if target.is_relative_to(x.parent)]
                        if ancestors:
                            selected.add(max(ancestors, key=lambda x: len(x.parts)))
        require(selected or args.changed, "selection contains no contract")
        available = {n for path in selected for n in contracts[path]["capabilities"]}
        require(set(args.capability) <= available, "unknown selected capability")
        results, capabilities = [], []
        matched_red = False
        for path in sorted(selected):
            rel = str(path.relative_to(root))
            data = contracts[path]
            for name, cap in data["capabilities"].items():
                if args.capability and name not in args.capability:
                    continue
                own = []
                for c in cap["checks"]:
                    if not args.all and c["kind"] not in ({"fast", "runtime"} if args.changed else {mode}):
                        continue
                    if args.record_red and c["id"] != args.record_red:
                        continue
                    matched_red = matched_red or c["id"] == args.record_red
                    h = digest(path, c, data.get("doctor", {}))
                    pp = proof_path(state, rel, c)
                    try:
                        proof = json.loads(pp.read_text())
                    except (OSError, ValueError):
                        proof = {}
                    observed_hash = None
                    if args.confirm_red and c["id"] == args.record_red:
                        require(args.confirm_red == c["red"], "confirmation must equal declared red reason")
                        require(proof.get("hash") == h and proof.get("phase") == "observed", "no matching observed red to confirm")
                        require(proof.get("failure_type") == "assertion", "infrastructure, timeout or missing adapter cannot prove red")
                        observed_hash = hashlib.sha256(proof["observed"].encode()).hexdigest()
                        require(args.confirm_observed == observed_hash, "--confirm-observed must match the recorded output hash")
                        proof.update(phase="confirmed", confirmed_reason=c["red"], confirmed_at=time.time())
                        save(pp, proof)
                    ok, observed, failure_type = execute(path, c, data.get("doctor", {}))
                    if args.record_red and not args.confirm_red and not ok and failure_type == "assertion":
                        proof = {"contract": rel, "id": c["id"], "hash": h, "phase": "observed", "observed": observed, "red": c["red"], "failure_type": failure_type, "time": time.time()}
                        save(pp, proof)
                    evidence = proof.get("hash") == h and proof.get("phase") == "confirmed"
                    status = "PASS" if ok and evidence else "PEND" if ok or failure_type == "pending" else "TIMEOUT" if failure_type == "timeout" else "FAIL"
                    r = {"contract": rel, "capability": name, "id": c["id"], "kind": c["kind"], "category": c.get("category", name), "status": status, "expected": c["expected"], "observed": observed, "evidence": str(pp) if evidence else None, "definition_hash": h, "failure_type": failure_type, "remedy": c["remedy"]}
                    if proof.get("phase") == "observed":
                        r["red_observed_sha256"] = hashlib.sha256(proof["observed"].encode()).hexdigest()
                    results.append(r)
                    own.append(r)
                complete = len(own) == len(cap["checks"])
                statuses = {r["id"]: r["status"] for r in own}
                required = set(cap["keep"] if "keep" in cap else [])
                required.update(x for x in cap["success"] if x != "keep")
                passed = complete and all(statuses.get(x) == "PASS" for x in required)
                capabilities.append({"contract": rel, "capability": name, "complete": complete, "success": passed, "note": "fully validated" if complete else "capability not fully validated by this partial selection"})
        require(not args.record_red or matched_red, "red check not in selection")
        code = 3 if any(r["status"] == "TIMEOUT" for r in results) else 1 if uncovered or not results or any(r["status"] != "PASS" for r in results) or args.all and any(not c["success"] for c in capabilities) else 0
        report = {"results": results, "capabilities": capabilities, "uncovered": uncovered, "summary": {"total": len(results), **{s.lower(): sum(r["status"] == s for r in results) for s in ("PASS", "FAIL", "PEND", "TIMEOUT")}, "exit_code": code}}
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            for r in results:
                print(f"{r['status']} [{r['category']}] {r['contract']}:{r['id']}\n  expected: {r['expected']}\n  observed: {r['observed']}\n  evidence: {r['evidence'] or 'red proof missing or invalidated'}\n  remedy: {r['remedy']}")
                if r.get("red_observed_sha256"):
                    print(f"  red observed SHA256: {r['red_observed_sha256']}")
            for c in capabilities:
                print(f"{c['capability']}: {c['note']}; success={c['success']}")
            if uncovered:
                print("Uncovered files: " + ", ".join(uncovered))
            print("FOR AGENTS")
            for r in results:
                if r["status"] != "PASS":
                    print(f"  {r['id']}: {r['remedy']}; confirm an observed, relevant red before accepting green")
            print(json.dumps(report["summary"]))
        return code
    except Invalid as e:
        print(str(e), file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
