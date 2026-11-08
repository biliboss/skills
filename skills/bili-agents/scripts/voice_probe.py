#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Probe the installed role/voice in independent non-interactive Claude sessions."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time


def main():
    skill = Path(__file__).resolve().parent.parent
    plugin = Path(os.environ.get("AG_PLUGIN_DIR", skill.parent.parent)).resolve()
    config = os.environ.get("AG_CLAUDE_CONFIG_DIR")
    if not config or not Path(config).is_dir():
        print("voice probe: set AG_CLAUDE_CONFIG_DIR to an existing authorized subscription configuration", file=sys.stderr)
        return 2
    try:
        timeout = float(os.environ.get("AG_VOICE_TIMEOUT", "120"))
        if timeout <= 0 or timeout > 600:
            raise ValueError()
    except ValueError:
        print("voice probe: AG_VOICE_TIMEOUT must be between 0 and 600 seconds", file=sys.stderr)
        return 2
    if not (plugin / ".claude-plugin/plugin.json").is_file():
        print("voice probe: AG_PLUGIN_DIR does not contain a plugin manifest", file=sys.stderr)
        return 2
    state = Path(os.environ.get("AG_VOICE_STATE", Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "bili-agents/voice"))
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    evidence = Path(tempfile.mkdtemp(prefix="probe-", dir=state))
    env = os.environ.copy()
    for key in list(env):
        if key in {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "ANTHROPIC_BASE_URL", "CLAUDECODE", "CLAUDE_CODE_SIMPLE", "CLAUDE_CODE_SAFE_MODE"}:
            env.pop(key, None)
    role = os.environ.get("AG_VOICE_ROLE", "qa")
    env.update(CLAUDE_CONFIG_DIR=config, AG_ROLE=role, AG_SKILL=str(skill), AG_SKILLS_DIR=str(skill.parent))
    hook = subprocess.run([str(skill / "scripts/session-start.sh")], env=env, capture_output=True, text=True, timeout=10)
    try:
        emitted = json.loads(hook.stdout)
        assert emitted["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError, AssertionError):
        print("voice probe: role hook did not emit context; inspect the selected role", file=sys.stderr)
        return 2
    (evidence / "role-emitted.json").write_text(json.dumps(emitted, indent=2) + "\n")
    voice = os.environ.get("AG_VOICE", "biliboss-skills:Bili")
    settings = {"outputStyle": voice, "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": shlex.quote(str(skill / "scripts/session-start.sh")), "timeout": 10}]}]}}
    settings_path = evidence / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    prompts = ["What is the difference between a health diagnosis and a behavior test?", "A teammate says a change is ready. What do you need before approving it?"]
    records = []
    cli = os.environ.get("AG_CLAUDE_BIN", "claude")
    code = 0
    with tempfile.TemporaryDirectory(prefix="ag-voice-cwd-") as cwd:
        for number, prompt in enumerate(prompts, 1):
            argv = [cli, "-p", prompt, "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--setting-sources", "", "--settings", str(settings_path), "--plugin-dir", str(plugin), "--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
            started = time.monotonic()
            try:
                run = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                (evidence / f"{number}.stdout.jsonl").write_text(stdout.decode() if isinstance(stdout, bytes) else stdout)
                (evidence / f"{number}.stderr.txt").write_text(stderr.decode() if isinstance(stderr, bytes) else stderr)
                records.append({"probe": number, "status": "TIMEOUT", "duration_s": time.monotonic() - started})
                code = 3
                break
            (evidence / f"{number}.stdout.jsonl").write_text(run.stdout)
            (evidence / f"{number}.stderr.txt").write_text(run.stderr)
            events = []
            for line in run.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            results = [event for event in events if event.get("type") == "result"]
            response = str(results[-1].get("result", "")) if results else ""
            init = next((event for event in events if event.get("type") == "system" and event.get("subtype") == "init"), {})
            words = len(re.findall(r"\S+", response))
            sentences = len([part for part in re.split(r"[.!?]+(?:\s|$)", response) if part.strip()])
            listed = bool(re.search(r"(?m)^\s*(?:[-*#]|\d+[.)])\s", response))
            success = run.returncode == 0 and bool(response.strip()) and words <= 60 and sentences <= 3 and not listed and not any(event.get("is_error") for event in results)
            runtime_style = init.get("output_style")
            infrastructure = bool(re.search(r"weekly limit|usage limit|not logged in|authentication|rate.limit", response, re.I))
            if infrastructure:
                code = 2
            role_loaded = False
            for event in events:
                if event.get("subtype") == "hook_response" and event.get("exit_code") == 0:
                    try:
                        context = json.loads(event.get("output") or event.get("stdout") or "{}")
                        role_loaded |= context.get("hookSpecificOutput", {}).get("additionalContext") == emitted["hookSpecificOutput"]["additionalContext"]
                    except (ValueError, TypeError):
                        pass
            if not role_loaded:
                success = False
            if runtime_style not in {voice, "Bili", "bili", "biliboss-skills:bili"}:
                success = False
            records.append({"probe": number, "prompt": prompt, "status": "PEND" if infrastructure else "PASS" if success else "FAIL", "returncode": run.returncode, "response": response, "words": words, "sentences": sentences, "lists_or_headings": listed, "runtime_style": runtime_style, "runtime_role_loaded": role_loaded, "session_id": init.get("session_id"), "duration_s": time.monotonic() - started})
            if not success:
                code = 2 if infrastructure else 1
                break
    report = {"role": role, "voice": voice, "plugin": str(plugin), "probes": records, "exit_code": code, "limitation": "Runtime role hook output is matched to emitted context. Behavioral bounds alone do not prove semantic role adherence."}
    (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"voice probe: {len(records)} fresh session(s), {'passed' if code == 0 else 'not approved'}; evidence: {evidence}")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"voice probe could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
