# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Ground skill edits in completed transcript loads and retro signals."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

RETRO = Path(__file__).resolve().parents[2] / "retro/scripts/retro.py"
spec = importlib.util.spec_from_file_location("retro_scanner", RETRO)
retro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retro)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def records(path):
    rows = []
    for number, line in enumerate(Path(path).expanduser().read_text().splitlines(), 1):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append((number, row))
    return rows


def skill_loads(path, skill):
    """Only a matched successful tool result proves a load, never a mention."""
    pending = {}
    found = []
    for line, row in records(path):
        content = (row.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if row.get("type") == "assistant" and block.get("type") == "tool_use":
                args = block.get("input") or {}
                name = block.get("name", "")
                loaded = False
                if name == "Read":
                    file_path = args.get("file_path", "")
                    loaded = (Path(file_path).name == "SKILL.md" and Path(file_path).parent.name == skill)
                elif name == "Skill":
                    loaded = args.get("skill", "").split(":")[-1] == skill
                if loaded and block.get("id"):
                    pending[block["id"]] = {"invocation_line": line, "tool": name,
                                             "input": args}
            elif row.get("type") == "user" and block.get("type") == "tool_result":
                load = pending.pop(block.get("tool_use_id"), None)
                text = retro._text(block.get("content"))
                if load and not block.get("is_error") and text.strip():
                    found.append({**load, "line": line, "excerpt": text[:500]})
    return found


def scan(path, skill):
    loads = skill_loads(path, skill)
    return {"session": str(Path(path).expanduser().resolve()), "skill": skill, "loads": loads,
            "signals": [{**row, "line": row["index"] + 1} for row in retro.scan(str(path), 10000)
                        if any(load["line"] <= row["index"] + 1 for load in loads)]}


def propose(skill_file, session, line, old, new):
    target = Path(skill_file).expanduser().resolve()
    skill = target.parent.name
    source = scan(session, skill)
    signals = [s for s in source["signals"] if s["line"] == line and s["kind"] != "praise"]
    if not signals:
        raise ValueError("no correction, marker or workaround after a completed skill load at that line")
    before = target.read_text()
    if not old.strip() or before.count(old) != 1 or old == new or not new.strip():
        raise ValueError("old must identify one nonempty passage and new must change it")
    if max(len(old), len(new)) > 1200 or max(old.count('\n'), new.count('\n')) > 12:
        raise ValueError("propose one small edit (at most 1200 characters and 13 lines)")
    load = [r for r in source["loads"] if r["line"] <= line][-1]
    return {"version": 1, "skill": skill, "target": str(target), "before_hash": digest(before),
            "old": old, "new": new, "evidence": {"session": source["session"],
            "session_hash": digest(Path(session).read_text()), "signal": signals[0], "load": load}}


def apply(proposal, doctor, timeout=120):
    data = json.loads(Path(proposal).read_text())
    target = Path(data["target"])
    if target.name != "SKILL.md":
        raise ValueError("only SKILL.md edits are supported")
    before = target.read_text()
    if digest(before) != data["before_hash"]:
        raise ValueError("skill changed since the proposal; propose again")
    evidence = data["evidence"]
    if digest(Path(evidence["session"]).read_text()) != evidence["session_hash"]:
        raise ValueError("source transcript changed; propose again")
    verified = propose(target, evidence["session"], evidence["signal"]["line"], data["old"], data["new"])
    if verified != data:
        raise ValueError("proposal evidence does not match the source")
    if not doctor:
        raise ValueError("an explicit doctor command is required")
    after = before.replace(data["old"], data["new"], 1)
    target.write_text(after)
    try:
        result = subprocess.run(doctor, cwd=target.parent, capture_output=True, text=True, timeout=timeout)
        status = {"applied": result.returncode == 0, "doctor_exit": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        status = {"applied": False, "doctor_exit": None, "error": str(exc)}
    if not status["applied"]:
        if target.read_text() != after:
            raise RuntimeError("doctor modified SKILL.md; refusing to overwrite concurrent changes")
        target.write_text(before)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    scan_parser = commands.add_parser("scan")
    scan_parser.add_argument("skill")
    scan_parser.add_argument("sessions", nargs="+")
    proposal_parser = commands.add_parser("propose")
    proposal_parser.add_argument("skill_file")
    proposal_parser.add_argument("--session", required=True)
    proposal_parser.add_argument("--line", type=int, required=True)
    proposal_parser.add_argument("--old", required=True)
    proposal_parser.add_argument("--new", required=True)
    proposal_parser.add_argument("--output", required=True)
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("proposal")
    apply_parser.add_argument("--timeout", type=float, default=120)
    apply_parser.add_argument("doctor", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == "scan":
            result = [scan(path, args.skill) for path in args.sessions]
        elif args.command == "propose":
            if Path(args.skill_file).name != "SKILL.md":
                raise ValueError("target must be SKILL.md")
            result = propose(args.skill_file, args.session, args.line, args.old, args.new)
            output = Path(args.output).expanduser()
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x") as f:
                os.chmod(output, 0o600)
                json.dump(result, f, ensure_ascii=False, indent=2)
        else:
            command = args.doctor[1:] if args.doctor[:1] == ["--"] else args.doctor
            result = apply(args.proposal, command, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command == "apply" and not result["applied"] else 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"self-learning: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
