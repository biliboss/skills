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

**Someone else's PR (any repo, no GitHub app needed):** when a web reviewer (ChatGPT, Codex) cannot reach an org's
repo, review it here with the owner's `gh` access: `gh repo clone <org>/<repo> <scratch>/repo -- --filter=blob:none`,
`gh pr checkout <n>` inside it, then `diff-review.sh . --base origin/main`. Also run the tests of the parts the diff
touches, because the reviewer lists them under "declined to judge" and never runs them. Report locally; never comment
on the PR unless asked (publishing outward is the owner's call).

Events: `review.started`, `finding.reported`, `finding.fixed`, `finding.dismissed`, `review.finished`.

## Never reported

Pre-existing code; what a linter, formatter or test catches; style outside the house rules; "may break other
code" with no visible path; symbols defined outside the diff; intended decisions; praise. A finding that a
framework already handles is not a finding: check it before acting.

## Tuning the engine

- **Keep a regression case per prompt rule.** A rule added to `references/review-prompt.md` must be re-run on the diff
  that motivated it and on at least one other diff before it ships: a rule tuned on one case can make the reviewer
  noisy elsewhere. The first case: the change that added `render_screens` must report the iframe URL taken from data
  with no scheme check and no sandbox (a security sink), and must not suggest re-escaping an attribute the framework
  already escapes.
- **Security sinks are findings even when today's data is ours**: a data value that becomes a URL, HTML, a path or a
  command without validation. Without that rule the reviewer judged the sink safe because the steps were authored
  in-house.
- **PR-Agent was measured and rejected as the engine** (local git provider, GLM): it missed the sink and proposed a
  double escape that would break `JSON.parse`. Its GLM route needs `ZAI_API_BASE` on the Coding Plan endpoint
  (`https://api.z.ai/api/coding/paas/v4`; the default endpoint bills per token) and `CONFIG__REASONING_EFFORT=low`;
  keep that for a second-opinion experiment only.

## After the review

1. Verify each finding against the code before touching it; the reviewer can be wrong.
2. Real: fix it in the worktree, commit, then `scripts/diff-review.sh fix <finding> --text "<commit and what changed>"`.
3. Not real: `scripts/diff-review.sh dismiss <finding> --reason false_positive|intended|out_of_scope --text "<why>"`.
4. After a fix, run the review again on the new diff. Blockers open: back to execute.
5. Three dismissals of the same reason: the CLI says so; propose a lesson to `retro` (the rule that would have
   prevented the noise, in this skill's prompt or house rules).

`scripts/diff-review.sh findings [--open]` lists the projected findings; `emit` is the validated raw writer. Call
`review.py` only through `diff-review.sh` or `uv run --script`: run bare, the shell executes it as a shell script
(its first line `import …` runs ImageMagick's `import`).

**A conflict you resolved by hand gets a review before the merge**: a mechanical "keep both sides" on a frontmatter
conflict leaves two `version:` keys, which the tests do not catch and the review does.

Tests: `uv run --script scripts/test_review.py` (a fake engine, no model call).
