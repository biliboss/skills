# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Review: an AI code review of a local git diff, before the delivery. Design stage, drawn in the dev-console as the
Review domain.

Code review is the practice (the literature's term); a finding's severity follows Conventional Comments' labels. The
review checks the code's quality; backbrief's verify (IV&V) checks that the delivery does what was asked. No
GitHub: the diff is the worktree's against its base, read with git.

Prototype: the journal is a global append-only JSONL, ~/.local/share/review/events.jsonl (override REVIEW_DIR); the
engine's full output lives beside it in runs/<id>.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

JOURNAL = Path(os.environ.get("REVIEW_DIR", "~/.local/share/review")).expanduser() / "events.jsonl"

EVENTS = {
    "review": {
        # Uma revisão começou sobre o diff de um worktree contra a base: a branch, o commit, o modelo (plano fixo) e a
        # tarefa do backbrief que gerou a mudança.
        "start": "started",
        # A revisão acabou: quanto tempo levou, quantos achados e quantos ficaram abertos; a saída inteira em runs/<id>.md.
        "finish": "finished",
    },
    "finding": {
        # Um achado: o arquivo e a linha, a gravidade (problema, sugestão, detalhe), a confiança e o texto, com a regra
        # da casa quando é uma delas.
        "report": "reported",
        # O achado foi corrigido no worktree, num commit.
        "fix": "fixed",
        # O achado foi descartado, com o motivo (falso positivo, de propósito, fora do escopo); três descartes iguais
        # viram proposta de lição para a retro.
        "dismiss": "dismissed",
    },
}

# The edges, in the order the story happens: a review starts, reports findings, each is fixed or dismissed, the review
# finishes; a finding fixed leads to a new review of the new diff.
TRANSITIONS = {
    "review.started": ["finding.reported", "review.finished"],
    "finding.reported": ["finding.fixed", "finding.dismissed"],
    "finding.fixed": ["review.finished"],
    "finding.dismissed": ["review.finished"],
    "review.finished": ["review.started"],
}


def _project(events: list[dict]) -> dict:
    """A finding as the journal leaves it: where it is, how serious, and how it ended."""
    if not events:
        return {}
    state = {"id": events[-1]["finding"], "file": "", "line": None, "severity": "", "text": "", "status": "",
             "updated_at": events[-1]["at"]}
    for e in events:
        v = e.get("value", {})
        kind = e["event"].split(".")[1]
        if kind == "reported":
            state.update(file=v.get("file", ""), line=v.get("line"), severity=v.get("severity", ""), text=v.get("text", ""),
                         confidence=v.get("confidence"), scenario=v.get("scenario", ""), worktree=v.get("worktree", ""),
                         review=e.get("review", ""))
        if kind == "dismissed":
            state["reason"] = v.get("reason", "")
        state["status"] = kind
    return state


class ReviewJournal:
    """Read-only view of the Review journal for the dev-console contract."""

    def _events(self) -> list[dict]:
        if not JOURNAL.exists():
            return []
        return [json.loads(line) for line in JOURNAL.read_text().splitlines() if line.strip()]

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        events = self._events()
        if "id" in query:
            matches = [e for e in events if e.get("finding") == query["id"]]
            return matches if query.get("history") else _project(matches)
        if "event" in query:
            return [e for e in events if e["event"] == query["event"]]
        if query.get("history"):
            return events
        groups: dict[str, list[dict]] = {}
        for e in events:
            if e.get("finding"):
                groups.setdefault(e["finding"], []).append(e)
        return [s for g in groups.values() if (s := _project(g))]


# ---- CLI: the only writer of the journal (uv run --script review.py run|emit|findings|fix|dismiss) ----

import argparse  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
SEVERITIES = ("blocker", "important", "minor")
REASONS = ("false_positive", "intended", "out_of_scope")
CONFIDENCE_CUT = 80
MAX_FINDINGS = 5
MAX_DIFF_CHARS = 200_000
LESSON_AFTER = 3
PI_TOOLS = "read,grep,find,ls"  # read-only: the reviewer looks at the code around the diff, never changes it
DEFAULT_MODEL = "sonnet"


def journal_path() -> Path:
    """The journal, read from REVIEW_DIR on every call."""
    return Path(os.environ.get("REVIEW_DIR", "~/.local/share/review")).expanduser() / "events.jsonl"


def _all_events() -> list[dict]:
    p = journal_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def emit(event: str, value: dict, finding: str | None = None, review: str | None = None, actor: str = "agent") -> dict:
    valid = {f"{d}.{k}" for d, kinds in EVENTS.items() for k in kinds.values()}
    if event not in valid:
        raise ValueError(f"unknown event {event!r}; one of {sorted(valid)}")
    if not isinstance(value, dict) or not value.get("text"):
        raise ValueError("value must be an object with a non-empty `text`")
    if event.startswith("finding.") and not finding:
        raise ValueError(f"{event} requires --finding <id>")
    row: dict[str, Any] = {"id": uuid.uuid4().hex[:12], "event": event}
    if review:
        row["review"] = review
    if finding:
        row["finding"] = finding
    row.update(at=datetime.now().astimezone().isoformat(timespec="seconds"), actor=actor, value=value)
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def findings(open_only: bool = False, worktree: str | None = None) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for e in _all_events():
        if e.get("finding"):
            groups.setdefault(e["finding"], []).append(e)
    out = [s for g in groups.values() if (s := _project(g))]
    if open_only:
        out = [s for s in out if s["status"] == "reported"]
    if worktree:
        out = [s for s in out if s["worktree"] == worktree]
    return out


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def dedupe_key(file: str, text: str) -> str:
    return f"{file}::{_norm(text)}"


def parse_output(text: str) -> tuple[list[dict], list[str]]:
    """The model's final JSON block -> (findings, declined). Fail-closed: anything off raises ValueError."""
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = blocks[-1] if blocks else None
    if candidate is None:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            candidate = stripped
    if candidate is None:
        raise ValueError("no final JSON block in the output")
    try:
        data = json.loads(candidate)
    except ValueError as ex:
        raise ValueError(f"final JSON block does not parse: {ex}") from ex
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        raise ValueError("final JSON must be an object with a `findings` list")
    out = []
    for i, f in enumerate(data["findings"]):
        if not isinstance(f, dict):
            raise ValueError(f"finding {i} is not an object")
        if not f.get("file") or not f.get("text") or f.get("severity") not in SEVERITIES:
            raise ValueError(f"finding {i} needs file, text and severity in {SEVERITIES}")
        conf = f.get("confidence")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            raise ValueError(f"finding {i} needs a numeric confidence")
        line = f.get("line")
        out.append({"file": str(f["file"]), "line": line if isinstance(line, int) else None, "severity": f["severity"],
                    "confidence": conf, "text": str(f["text"]), "scenario": str(f.get("scenario") or ""),
                    "rule": str(f.get("rule") or "")})
    declined = [str(x) for x in data.get("declined") or []]
    return out, declined


def select(found: list[dict], previous: list[dict]) -> list[dict]:
    """Keep what is confident, new to this worktree's open or dismissed findings, most serious first, at most 5."""
    seen = {dedupe_key(p["file"], p["text"]) for p in previous if p["status"] in ("reported", "dismissed")}
    kept, keys = [], set()
    for f in sorted(found, key=lambda f: (SEVERITIES.index(f["severity"]), -f["confidence"])):
        k = dedupe_key(f["file"], f["text"])
        if f["confidence"] < CONFIDENCE_CUT or k in seen or k in keys:
            continue
        keys.add(k)
        kept.append(f)
    return kept[:MAX_FINDINGS]


def build_prompt(diff: str, previous: list[dict]) -> str:
    ref = SKILL_DIR / "references"
    prior = "\n".join(f"- [{p['status']}{'/' + p['reason'] if p.get('reason') else ''}] {p['file']}: {p['text']}"
                      for p in previous) or "(none)"
    return (f"{(ref / 'review-prompt.md').read_text()}\n## HOUSE RULES\n{(ref / 'house-rules.md').read_text()}\n"
            f"## PREVIOUS FINDINGS (same worktree; do not repeat them)\n{prior}\n\n## DIFF\n```diff\n{diff}\n```\n")


def _git(wt: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", wt, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _registry():
    """The house's model registry lives in backbrief's tasks.py; import it, never copy the table."""
    path = str(SKILL_DIR.parent / "backbrief" / "scripts")
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import tasks  # noqa: PLC0415
    except ImportError as ex:
        raise ValueError(f"the model registry needs skills/backbrief beside this skill: {ex}") from ex
    return tasks


def call_pi(prompt: str, worktree: str, spec: dict) -> tuple[str, str]:
    """Run the review through pi on a flat-plan model, in the worktree. Returns (final assistant text, error)."""
    fake = os.environ.get("DIFF_REVIEW_FAKE_OUTPUT")
    if fake:
        return Path(fake).read_text(), ""
    tasks = _registry()
    try:
        env = {**os.environ, **tasks._model_env(spec)}  # the key goes to the child only, never printed
    except RuntimeError as ex:
        return "", str(ex)
    env.pop("ANTHROPIC_API_KEY", None)  # the subscription, never per-token billing
    cmd = ["pi", "-p", "--no-session", "--mode", "json", "--model", spec["model"], "--tools", PI_TOOLS, prompt]
    try:
        done = subprocess.run(cmd, cwd=worktree, env=env, capture_output=True, text=True,
                              timeout=int(os.environ.get("DIFF_REVIEW_TIMEOUT", "900")))
    except (OSError, subprocess.TimeoutExpired) as ex:
        return "", f"pi failed: {ex}"
    answer = ""
    for line in done.stdout.splitlines():  # pi's --mode json stream: one JSON object per line
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        m = rec.get("message") or {}
        if rec.get("type") == "message_end" and m.get("role") == "assistant":
            answer = "".join(b.get("text", "") for b in m.get("content", []) if b.get("type") == "text") or answer
    if done.returncode != 0 and not answer:
        return "", f"pi exit {done.returncode}: {done.stderr.strip()[:300]}"
    return answer, ""


def run(worktree: str, base: str, task: str | None, model: str = DEFAULT_MODEL) -> int:
    try:
        spec = _registry().resolve_model(model)
    except ValueError as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    wt = str(Path(worktree).expanduser().resolve())
    try:
        if _git(wt, "status", "--porcelain", "--untracked-files=no").strip():
            print("Árvore suja: faça o commit (ou stash) antes de revisar; a revisão lê o diff commitado.", file=sys.stderr)
            return 2
        merge_base = _git(wt, "merge-base", base, "HEAD").strip()
        diff = _git(wt, "diff", "--unified=20", f"{merge_base}...HEAD")
        branch = _git(wt, "rev-parse", "--abbrev-ref", "HEAD").strip()
        commit = _git(wt, "rev-parse", "--short", "HEAD").strip()
    except RuntimeError as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    if not diff.strip():
        print(f"Diff vazio: {branch} não tem nada além de {base}; nada a revisar.", file=sys.stderr)
        return 2
    if len(diff) > MAX_DIFF_CHARS:
        print(f"Diff grande demais ({len(diff)} caracteres, limite {MAX_DIFF_CHARS}): divida a mudança.", file=sys.stderr)
        return 2
    review_id = uuid.uuid4().hex[:8]
    previous = findings(worktree=wt)
    emit("review.started", {"text": f"review of {branch}@{commit} against {base}", "worktree": wt, "branch": branch,
                            "commit": commit, "base": base, "model": spec["model"], "task": task or ""},
         review=review_id, actor="diff-review")
    t0 = time.time()
    output, error = call_pi(build_prompt(diff, previous), wt, spec)
    runs = journal_path().parent / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{review_id}.md").write_text(output or f"(no output) {error}\n")
    kept: list[dict] = []
    declined: list[str] = []
    if not error:
        try:
            found, declined = parse_output(output)
            kept = select(found, previous)
        except ValueError as ex:
            error = str(ex)
    duration = round(time.time() - t0, 1)
    if error:
        emit("review.finished", {"text": f"review failed: {error}", "error": error, "findings": 0, "open": 0,
                                 "duration_s": duration, "model": spec["model"]}, review=review_id, actor="diff-review")
        print(f"Revisão falhou ({error}). Saída em {runs / (review_id + '.md')}.", file=sys.stderr)
        return 2
    for f in kept:
        emit("finding.reported", {**f, "worktree": wt}, finding=uuid.uuid4().hex[:8], review=review_id, actor="diff-review")
    open_now = findings(open_only=True, worktree=wt)
    emit("review.finished", {"text": f"{len(kept)} new finding(s), {len(open_now)} open", "findings": len(kept),
                             "open": len(open_now), "duration_s": duration, "model": spec["model"],
                             "declined": declined}, review=review_id, actor="diff-review")
    print(f"Revisão {review_id} de {branch}@{commit}: {len(kept)} achado(s) novo(s), {len(open_now)} aberto(s), {duration}s.")
    for s in open_now:
        print(f"  [{s['severity']}] {s['id']} {s['file']}:{s['line']} {s['text']}")
    for d in declined:
        print(f"  (não julgou) {d}")
    print(f"Saída completa: {runs / (review_id + '.md')}")
    return 1 if any(s["severity"] == "blocker" for s in open_now) else 0


def close(finding_id: str, kind: str, text: str, extra: dict | None = None) -> dict:
    cur = [s for s in findings() if s["id"] == finding_id]
    if not cur:
        raise ValueError(f"unknown finding {finding_id!r}")
    if cur[0]["status"] != "reported":
        raise ValueError(f"finding {finding_id} is already {cur[0]['status']}")
    return emit(f"finding.{EVENTS['finding'][kind]}", {"text": text, **(extra or {})}, finding=finding_id, actor="agent")


def dismissals(reason: str) -> int:
    return sum(1 for s in findings() if s["status"] == "dismissed" and s["reason"] == reason)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="review.py", description="Review journal: the only writer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("worktree")
    r.add_argument("--base", default="origin/main")
    r.add_argument("--task")
    r.add_argument("--model", default=DEFAULT_MODEL, help="a registry id of backbrief: sonnet (default) or glm")
    e = sub.add_parser("emit")
    e.add_argument("event")
    e.add_argument("value")
    e.add_argument("--finding")
    e.add_argument("--review")
    e.add_argument("--actor", required=True)
    f = sub.add_parser("findings")
    f.add_argument("--open", action="store_true")
    f.add_argument("--worktree")
    x = sub.add_parser("fix")
    x.add_argument("finding")
    x.add_argument("--text", required=True)
    d = sub.add_parser("dismiss")
    d.add_argument("finding")
    d.add_argument("--reason", required=True, choices=REASONS)
    d.add_argument("--text", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "run":
            return run(a.worktree, a.base, a.task, a.model)
        if a.cmd == "emit":
            print(json.dumps(emit(a.event, json.loads(a.value), a.finding, a.review, a.actor), ensure_ascii=False))
        elif a.cmd == "findings":
            print(json.dumps(findings(a.open, a.worktree), ensure_ascii=False, indent=2))
        elif a.cmd == "fix":
            print(json.dumps(close(a.finding, "fix", a.text), ensure_ascii=False))
        else:
            print(json.dumps(close(a.finding, "dismiss", a.text, {"reason": a.reason}), ensure_ascii=False))
            if dismissals(a.reason) >= LESSON_AFTER:
                print(f"{dismissals(a.reason)} descartes '{a.reason}': proponha uma lição à retro "
                      f"(lesson.proposed, skill diff-review).", file=sys.stderr)
    except (ValueError, OSError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
