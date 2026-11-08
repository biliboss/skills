# self-learning

Improve one skill from its actual use, with a reviewable edit and a doctor that decides whether it stays.
The [skill instructions](SKILL.md) define the evidence and approval rules.

```sh
scripts/self-learning.sh scan example /path/to/session.jsonl
scripts/self-learning.sh propose /path/to/example/SKILL.md \
  --session /path/to/session.jsonl --line 42 \
  --old 'Inspect state before sending work.' \
  --new 'Inspect state before every send, including retries.' \
  --output "$HOME/.local/state/self-learning/proposal.json"
# After explicit acceptance, with the relevant full doctor:
scripts/self-learning.sh apply "$HOME/.local/state/self-learning/proposal.json" -- \
  uv run --script /path/to/doctor/scripts/contracts.py --all
```

`scan` returns session-local load and signal locations; `propose` writes a private JSON proposal without editing
its target; `apply` verifies that evidence and target are unchanged, applies one passage, and runs the supplied
command. JSON output reports whether the edit was retained. Exit codes are 0 success, 1 doctor rejection with
rollback, and 2 invalid input or stale evidence. The scanner currently understands Claude Code transcripts only.

Run the isolated checks:

```sh
uv run --script scripts/test_self_learning.py
```

They exercise successful and failed loads, mentions, stale and forged proposals, rejection with rollback and
acceptance with a green command. Source fixtures contain synthetic text, not private transcripts.

[Changelog](CHANGELOG.md)

## Sources

- [Retro](../retro/SKILL.md): its existing correction and workaround scanner is imported, not copied.
- [US Army after-action review](https://armypubs.army.mil/): compare expected and observed behavior before changing a procedure.
