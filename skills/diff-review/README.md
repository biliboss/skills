# diff-review

A code review of a local git diff before the delivery: our own prompt, run through pi on the Claude subscription
(or GLM), findings logged as events in `~/.local/share/review/events.jsonl`. The rules are in [SKILL.md](SKILL.md).

| Command | Example |
|---|---|
| review a worktree | `scripts/diff-review.sh ../repo.task-x --base origin/main --task <id>` |
| list findings | `scripts/diff-review.sh findings --open` |
| fix / dismiss | `scripts/diff-review.sh fix <id> --text "..."`; `scripts/diff-review.sh dismiss <id> --reason intended --text "..."` |

Tests: `uv run --script scripts/test_review.py`. History: [CHANGELOG.md](CHANGELOG.md).
