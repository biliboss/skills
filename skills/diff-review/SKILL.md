---
name: diff-review
description: >-
  Use when the owner says "diff-review", "revisa o diff", "revisão de código" or "code review local", and between
  verify and deliver in backbrief. An AI code review of a local git diff (a worktree against its base) with our
  own prompt, run through pi on a flat-plan model; it reports only problems the diff introduced, each with a concrete
  failure scenario, and logs them as events. Differs from backbrief's verify (does the delivery do what was
  asked) and from retro (lessons of the session).
metadata:
  version: 0.1.0
---

# diff-review

The owner-facing text is in Portuguese (Brazil). The journal is global, `~/.local/share/review/events.jsonl`
(override `REVIEW_DIR`); the only writer is `scripts/review.py`, run through `scripts/diff-review.sh`. The engine is
our own prompt ([references/review-prompt.md](references/review-prompt.md) plus
[references/house-rules.md](references/house-rules.md)), not PR-Agent; the choices are in
[references/prior-art.md](references/prior-art.md).

## When

Between verify and deliver of backbrief: verify asks "does it do what was asked", this asks "is the code
sound". A delivery with an **open blocker** goes back to execute. It also runs on any local branch on request.

## Run

```
scripts/diff-review.sh <worktree> [--base origin/main] [--task <id>] [--model sonnet|glm]
```

It refuses a dirty tree and an empty diff. It reads `git diff --unified=20 <merge-base>...HEAD`, adds the house
rules and the worktree's previous findings (so nothing is repeated), runs
`pi -p --no-session --mode json --model <registry model>` in the worktree with read-only tools, and keeps the
findings with confidence >= 80 (at most 5). `--model` is an id of backbrief's registry (default `sonnet`, the
mukutu subscription through the claude bridge; `glm` is the GLM Coding Plan; per-token providers are refused). The full
output is in `runs/<review id>.md`. Exit: 0 no open blocker, 1 an open blocker, 2 refused or the output was not
parsable (fail-closed: never read as "no findings").

Events: `review.started`, `finding.reported`, `finding.fixed`, `finding.dismissed`, `review.finished`.

## Never reported

Pre-existing code; what a linter, formatter or test catches; style outside the house rules; "may break other
code" with no visible path; symbols defined outside the diff; intended decisions; praise. A finding that a
framework already handles is not a finding: check it before acting.

## After the review

1. Verify each finding against the code before touching it; the reviewer can be wrong.
2. Real: fix it in the worktree, commit, then `scripts/diff-review.sh fix <finding> --text "<commit and what changed>"`.
3. Not real: `scripts/diff-review.sh dismiss <finding> --reason false_positive|intended|out_of_scope --text "<why>"`.
4. After a fix, run the review again on the new diff. Blockers open: back to execute.
5. Three dismissals of the same reason: the CLI says so; propose a lesson to `retro` (the rule that would have
   prevented the noise, in this skill's prompt or house rules).

`scripts/diff-review.sh findings [--open]` lists the projected findings; `emit` is the validated raw writer.

Tests: `uv run --script scripts/test_review.py` (a fake engine, no model call).
