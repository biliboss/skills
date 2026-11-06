# /// script
# requires-python = ">=3.11"
# ///
"""Routing eval of backbrief descriptions on pi (see references/evals.md).

Each variant is a copy of the skill with only the description changed, loaded beside the other real skills
(`--no-skills` + one `--skill` each) so it competes as in real use. Each run gets a work request in its own temp
dir. PASS = the requested file was not created and the final answer asks for the confirmation (the skill's own flow
writes a helper .sh, so "wrote any file" is the wrong test).

usage: uv run --script route_eval.py <haiku|sonnet> [variant ...]
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]  # .../skills
PI = SKILLS / "pi/scripts/pi-claude.sh"
OUT = Path(tempfile.gettempdir()) / "route-eval"
MODELS = {"haiku": "claude-bridge/claude-haiku-5-5", "sonnet": "claude-bridge/claude-sonnet-5-5"}

# None = the description as it is now. Add wordings here.
V = {
    "current": None,
    "gate": "Gate before any build or write request. When the user asks you to create, write, build, implement or "
            "change something, do not start: first repeat back what you understood (teach-back) and wait for the "
            "confirmation. Questions and one-line commands skip the gate.",
    "first-step": "Required first step of every task the user gives you: before any tool call that writes, repeat "
                  "the task back the way you understood it and wait for the confirmation. Only questions and "
                  "one-line commands go straight.",
}
PROMPTS = [  # (prompt, the file it asks for)
    ("Escreve um script em {d}/renomear-fotos.sh que renomeia as fotos de uma pasta pela data EXIF.", "renomear-fotos.sh"),
    ("Preciso que você crie em {d}/backup.sh um script que compacta a pasta ~/biliboss/.wiki num zip com a data no nome.", "backup.sh"),
]


def variant(name: str, desc: str | None) -> Path:
    dst = OUT / "skills" / name / "backbrief"
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(SKILLS / "backbrief", dst)
    if desc is not None:
        s = (dst / "SKILL.md").read_text()
        a, b = s.index("description: >-\n"), s.index("metadata:\n")
        body = textwrap.indent(textwrap.fill(desc, 110), "  ")  # word boundaries: a folded scalar splits mid-word breaks
        (dst / "SKILL.md").write_text(s[:a] + "description: >-\n" + body + "\n" + s[b:])
    return dst


def run(model: str, name: str, skill: Path, k: int) -> dict:
    work = Path(tempfile.mkdtemp(prefix=f"{name}-{k}-", dir=OUT))
    prompt, target = PROMPTS[k]
    args = ["bash", str(PI), "mukutu", "-p", "--no-session", "--mode", "json", "--model", MODELS[model], "--no-skills"]
    for p in [p for p in SKILLS.iterdir() if (p / "SKILL.md").exists() and p.name != "backbrief"] + [skill]:
        args += ["--skill", str(p)]
    args.append(prompt.format(d=work))
    log = work.with_suffix(".jsonl")
    try:
        with log.open("w") as f:
            subprocess.run(args, cwd=work, stdout=f, stderr=subprocess.STDOUT, timeout=240)
    except subprocess.TimeoutExpired:
        pass
    final = ""
    for line in log.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "agent_end":
            final = " ".join(c.get("text", "") for c in e["messages"][-1].get("content", []) if c.get("type") == "text")
    made = (work / target).exists()
    asks = bool(re.search(r"bate\?|confirm|entendi", final, re.I))
    return {"variant": name, "prompt": k, "pass": asks and not made, "made": made, "final": final[:120]}


def main() -> None:
    model, names = sys.argv[1], sys.argv[2:] or list(V)
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(n, variant(n, V[n]), k) for n in names for k in range(len(PROMPTS))]
    with ThreadPoolExecutor(5) as ex:
        res = list(ex.map(lambda j: run(model, *j), jobs))
    for r in res:
        print(f"{'PASS' if r['pass'] else 'fail'}  {r['variant']:<14} p{r['prompt']}  made={r['made']!s:<5} {r['final'][:80]}")
    by: dict[str, list[bool]] = {}
    for r in res:
        by.setdefault(r["variant"], []).append(r["pass"])
    print("\n" + "\n".join(f"{n:<14} {sum(v)}/{len(v)}" for n, v in by.items()))


if __name__ == "__main__":
    main()
