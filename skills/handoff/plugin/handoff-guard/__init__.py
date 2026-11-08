"""handoff-guard: keeps a long Hermes session from running past its context.

Opt-in per repo: ``HANDOFF_AT=<percent>`` in ``<git toplevel>/.wiki/wiki.config``, else in the ``wiki.config`` of
the ``$WIKI_HOME`` project (default ``~/wiki``) whose ``REPO=`` matches the toplevel's origin remote, else
``<git toplevel>/.biliboss`` (shell ``KEY=value`` files). No key, not a git repo, or anything unreadable: the hooks do nothing.

- ``post_api_request`` records the REAL context use of the session (``usage.prompt_tokens`` of the last request and the
  model's ``context_length``) in ``$HANDOFF_GUARD_STATE`` (default ``~/.local/state/handoff-guard``). The
  ``pre_llm_call`` payload carries no agent, so this is how the plugin sees what the TUI bar shows (``244.6k/1M``).
- ``pre_llm_call`` at used% >= HANDOFF_AT injects, once per crossing, the order to run the handoff on itself;
  at used% >= HANDOFF_AT + 15 it blocks the turn, unless the user message is itself about the handoff (it contains
  the word ``handoff`` or ``handoff.sh``): that message must reach the agent so it can run the command.
- A session that has not made an API call yet (first turn of a resumed session) has no number: nothing happens.

Never raises: every internal error returns None.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

BLOCK_MARGIN = 15
_KEY = "HANDOFF_AT"
_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE.parent.parent / "scripts" / "handoff.sh"   # skills/handoff/scripts/handoff.sh (plugin is symlinked)
_ESCAPE = re.compile(r"handoff", re.IGNORECASE)


def _state_dir() -> Path:
    return Path(os.environ.get("HANDOFF_GUARD_STATE") or Path.home() / ".local/state/handoff-guard")


def _state_file(session_id: str) -> Path:
    return _state_dir() / re.sub(r"[^A-Za-z0-9._-]", "_", session_id)


def _read_state(session_id: str) -> dict:
    try:
        data = json.loads(_state_file(session_id).read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_state(session_id: str, data: dict) -> None:
    path = _state_file(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def _toplevel(cwd: str) -> Path | None:
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             timeout=3, check=False)
        return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:
        return None


def _key_of(path: Path, key: str = _KEY) -> str | None:
    for line in path.read_text().splitlines():
        m = re.match(rf"\s*(?:export\s+)?{key}=(.*)$", line)
        if m:
            return m.group(1).split("#")[0].strip().strip("'\"")
    return None


def _origin_repo(top: Path) -> str | None:
    """owner/name of the toplevel's origin remote (github ssh or https, .git optional), else None."""
    out = subprocess.run(["git", "-C", str(top), "remote", "get-url", "origin"],
                         capture_output=True, text=True, timeout=3, check=False)
    if out.returncode != 0:
        return None
    url = out.stdout.strip()
    for pre in ("git@github.com:", "https://github.com/"):
        if url.startswith(pre):
            return url[len(pre):].removesuffix(".git")
    return None


def _central_wiki_config(top: Path) -> Path | None:
    """wiki.config of the $WIKI_HOME project whose REPO= is the toplevel's origin, else None."""
    repo = _origin_repo(top)
    home = Path(os.path.expanduser(os.environ.get("WIKI_HOME") or "~/wiki"))
    if not (repo and home.is_dir()):
        return None
    for cfg in sorted(home.glob("*/wiki.config")):
        try:
            if cfg.is_file() and _key_of(cfg, "REPO") == repo:
                return cfg
        except OSError:
            continue
    return None


def threshold(cwd: str | None = None) -> float | None:
    """HANDOFF_AT (percent) of the folder's git repo, or None when not opted in."""
    try:
        top = _toplevel(cwd or os.environ.get("TERMINAL_CWD") or os.getcwd())
        if top is None:
            return None
        for f in (top / ".wiki/wiki.config", _central_wiki_config(top), top / ".biliboss"):
            if f is not None and f.is_file():
                value = _key_of(f)
                if value:
                    pct = float(value)
                    return pct if 0 < pct <= 100 else None
        return None
    except Exception:
        return None


def record_usage(**kw) -> None:
    """post_api_request: remember the real prompt size and the model's window."""
    try:
        sid = kw.get("session_id")
        usage = kw.get("usage") or {}
        used = usage.get("prompt_tokens") or usage.get("input_tokens")
        window = kw.get("context_length")
        if not (sid and isinstance(used, (int, float)) and used > 0 and isinstance(window, (int, float)) and window > 0):
            return
        if threshold() is None:   # not opted in: write nothing
            return
        state = _read_state(sid)
        state.update(used=int(used), window=int(window))
        _write_state(sid, state)
    except Exception:
        return


def _command(session_id: str) -> str:
    return f"{_SCRIPT} --from {session_id} --detach"


def check(**kw):
    """pre_llm_call: inject at HANDOFF_AT, block at HANDOFF_AT + 15."""
    try:
        sid = kw.get("session_id")
        if not sid:
            return None
        at = threshold()
        if at is None:
            return None
        state = _read_state(sid)
        used, window = state.get("used"), state.get("window")
        if not (isinstance(used, int) and isinstance(window, int) and window > 0):
            return None
        pct = used * 100 / window
        if pct < at:
            if state.get("injected"):   # back under the line (compression): the next crossing injects again
                state["injected"] = False
                _write_state(sid, state)
            return None
        cmd = _command(sid)
        message = str(kw.get("user_message") or "")
        if pct >= at + BLOCK_MARGIN and not _ESCAPE.search(message):
            return {"action": "block", "message": (
                f"Handoff required: this session is at {pct:.0f}% of its context (limit {at + BLOCK_MARGIN:.0f}%). "
                f"Say \"handoff\" (or run `{cmd}`) and the agent hands the session over; "
                f"then continue in the clean session.")}
        if state.get("injected"):
            return None
        state["injected"] = True
        _write_state(sid, state)
        return {"context": (
            f"[handoff-guard] This session is at {pct:.0f}% of its context (HANDOFF_AT={at:g}%). Finish the current "
            f"step, then hand the session over on yourself: run `{cmd}` (it logs the session, opens a branch tab to "
            f"the right and sends /new with a summary). Do not start new work before it.")}
    except Exception:
        return None


def register(ctx):
    ctx.register_hook("post_api_request", record_usage)
    ctx.register_hook("pre_llm_call", check)
