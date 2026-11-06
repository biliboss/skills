"""The console's side of the flight recorder (DevConsole.app writes it; see SKILL.md, "Agent API").

`<recorder dir>/events.jsonl` holds the last 20 navigations of the app window, one JSON line each, with a PNG per line
in `shots/`. This module only READS it, plus asks the app for a fresh snapshot (`window.sh shot`) or, when the app is
not running, takes a headless one with check.py. Routes are registered by `register(rt, json_response)`.
Nothing here leaves the machine.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
KEEP = 20


def recorder_dir() -> Path:
    o = os.environ.get("DEV_CONSOLE_RECORDER_DIR")
    return Path(o).expanduser() if o else Path.home() / ".local/state/dev-console/recorder"


def read_lines(d: Path | None = None) -> list[dict]:
    """The last KEEP lines as dicts; a broken line is skipped, a missing file is an empty list."""
    f = (d or recorder_dir()) / "events.jsonl"
    try:
        raw = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for text in raw[-KEEP:]:
        try:
            v = json.loads(text)
        except ValueError:
            continue
        if isinstance(v, dict):
            out.append(v)
    return out


def now(d: Path | None = None) -> dict:
    lines = read_lines(d)
    return lines[-1] if lines else {"error": "no lines yet (is DevConsole.app running?)"}


def history(n: int = 5, d: Path | None = None) -> list[dict]:
    n = max(1, min(int(n), KEEP))
    return read_lines(d)[-n:]


def app_running() -> bool:
    return subprocess.run([str(SCRIPTS / "window.sh"), "running"], capture_output=True).returncode == 0


def ask_app_for_shot(timeout: float = 15.0) -> bool:
    """`window.sh shot` then `wait`: True when the app applied it."""
    w = str(SCRIPTS / "window.sh")
    if subprocess.run([w, "shot"], capture_output=True, timeout=timeout).returncode != 0:
        return False
    return subprocess.run([w, "wait"], capture_output=True, timeout=timeout).returncode == 0


def headless_shot(url: str, d: Path | None = None) -> dict:
    """A shot with check.py (a separate Chrome, so the app's window, domain and clock are untouched).
    The line is returned but NOT appended to events.jsonl: the ring is the app window's history only."""
    d = d or recorder_dir()
    t = datetime.now(timezone.utc)
    at = t.strftime("%Y%m%dT%H%M%S.") + f"{t.microsecond // 1000:03d}Z"
    shot = d / "shots" / f"{at}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run([str(SCRIPTS / "check.sh"), url, "--shot", str(shot)], capture_output=True, text=True, timeout=90)
        res = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        res = {"errors": [f"check: {type(e).__name__}"]}
    return {"at": at, "url": url, "domain": None, "module": None, "event": None, "widget": None, "width": 1000, "height": 800,
            "errors": res.get("errors", []), "shot": str(shot) if shot.exists() else None, "source": "headless"}


def fresh_shot(default_url: str, d: Path | None = None) -> dict:
    """source=app when the app took the snapshot; source=headless (and a `note`) when it is not running."""
    if app_running():
        before = now(d).get("at")
        if ask_app_for_shot():
            line = now(d)
            if line.get("at") != before and "error" not in line:
                return {**line, "source": "app"}
    line = headless_shot(read_lines(d)[-1]["url"] if read_lines(d) else default_url, d)
    return {**line, "note": "DevConsole.app did not answer: headless snapshot, not added to the ring"}


def own_url() -> str:
    """This console's own root, from its --port flag (the default page of a headless fallback)."""
    port = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--port"), "5057")
    return f"http://127.0.0.1:{port}/"


def register(rt, json_response, base_url=own_url):
    """The three read-only routes. `rt` is the console's route decorator, `json_response(data, status)` its JSON helper."""

    @rt("/agent/now")
    def agent_now():
        line = now()
        return json_response(line, 404 if "error" in line else 200)

    @rt("/agent/history")
    def agent_history(n: int = 5):
        return json_response(history(n))

    @rt("/agent/shot")
    def agent_shot():
        return json_response(fresh_shot(base_url()))

    return agent_now, agent_history, agent_shot


if __name__ == "__main__":  # a quick look: console_recorder.py [n]
    print(json.dumps(history(int(sys.argv[1]) if len(sys.argv) > 1 else 5)))
