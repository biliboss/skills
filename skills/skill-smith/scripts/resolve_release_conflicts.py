# /// script
# requires-python = ">=3.11"
# ///
"""Resolve the bookkeeping conflicts of a rebase in biliboss/skills by meaning, never by side.

usage: resolve_release_conflicts.py <worktree> <skill> <skill version> <plugin version>

- skills/<skill>/CHANGELOG.md and the root CHANGELOG.md: main's side stays as is; this branch's entries go into a
  new version block on top (<skill version> / <plugin version>).
- .claude-plugin/plugin.json: main's side (its description names the other skills), then `version` = <plugin version>
  and `./skills/<skill>` kept in `skills`.
- skills/<skill>/SKILL.md: prose conflicts keep both sides (main first); `metadata.version` = <skill version>, once.

Any other conflicted file (code) is left alone and listed: resolve it by hand, then compile and run the tests.
"""
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

R, SKILL, SV, PV = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
RX = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S)
TODAY = date.today().isoformat()


def split(text):
    """main's resolution of every hunk, and this branch's hunks."""
    return RX.sub(lambda m: m[1], text), [m[2] for m in RX.finditer(text)]


def on_top(text, block):
    i = text.index("## [")
    return text[:i] + block + text[i:]


done = []
p = R / f"skills/{SKILL}/CHANGELOG.md"
if p.exists() and "<<<<<<<" in p.read_text():
    ours, theirs = split(p.read_text())
    body = "".join(theirs).strip("\n")
    body = re.sub(r"^## \[[^\]]*\][^\n]*\n+", "", body)
    if not body.lstrip().startswith("###"):
        body = "### Changed\n\n" + body
    p.write_text(on_top(ours, f"## [{SV}] - {TODAY}\n\n{body}\n\n"))
    done.append(str(p))

p = R / "CHANGELOG.md"
if "<<<<<<<" in p.read_text():
    ours, theirs = split(p.read_text())
    lines = [l for t in theirs for l in t.splitlines() if l.startswith("- ")]
    lines = [re.sub(rf"`{re.escape(SKILL)}` \d+\.\d+\.\d+", f"`{SKILL}` {SV}", l) for l in lines]
    p.write_text(on_top(ours, f"## [{PV}] - {TODAY}\n\n### Changed\n\n" + "\n".join(lines) + "\n\n"))
    done.append(str(p))

p = R / ".claude-plugin/plugin.json"
s = p.read_text()
if "<<<<<<<" in s:
    s = RX.sub(lambda m: m[1], s)
d = json.loads(s)
d["version"] = PV
if f"./skills/{SKILL}" not in d.get("skills", []) and (R / f"skills/{SKILL}").is_dir():
    d.setdefault("skills", []).append(f"./skills/{SKILL}")
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
done.append(str(p))

p = R / f"skills/{SKILL}/SKILL.md"
if p.exists():
    s = RX.sub(lambda m: m[1] + m[2], p.read_text())
    s = re.sub(r"\n  version: \d+\.\d+\.\d+(\n  version: \d+\.\d+\.\d+)*", f"\n  version: {SV}", s, count=1)
    p.write_text(s)
    done.append(str(p))

left = subprocess.run(["git", "-C", str(R), "diff", "--name-only", "--diff-filter=U"], capture_output=True, text=True).stdout.split()
left = [f for f in left if str(R / f) not in done]
print("resolved:", *done, sep="\n  ")
print("left for you:", *(left or ["none"]), sep="\n  ")
