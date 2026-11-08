---
name: retro
description: >-
  Use when the owner says "retro", "/retro", "faz a retro", "o que aprendemos" or "lições da sessão". An
  after-action review of the session; it finds the owner's corrections, rework and workarounds, proposes them as
  rules for the skills they belong to, asks him to pick, and applies the accepted ones in one PR. Differs from
  skill-smith (how to write a skill; retro uses it to apply) and from postmortem (one error, read from NATS events).
metadata:
  version: 0.1.1
---

# retro

The owner-facing text (the ask, the report) is in Portuguese (Brazil). The journal is global,
`~/.local/share/retro/events.jsonl` (override `RETRO_DIR`); the only writer is `scripts/retro.py`
(stdlib, run through `scripts/retro.sh`). Sources and the reasoning: [references/prior-art.md](references/prior-art.md).

```
scripts/retro.sh  emit <event> '{"text": "...", ...}' [--lesson <id>] --actor <who>
scripts/retro.sh  lessons [--status S]
scripts/retro.sh  rejected-rules
scripts/retro.sh  scan <session.jsonl> [--max N]
```

## Steps

1. **Start.** `emit retro.started '{"text": "<scope>"}' --actor <you>`.
2. **Find the lessons.** Read the conversation in context. If it was compacted, or the owner asks for older
   sessions, run `scan` on `~/.claude/projects/<dir>/<session>.jsonl` (Claude Code deletes sessions after ~30 days:
   run `/retro` early) and read the surrounding messages of each hit. Signals, strongest first: an explicit marker
   ("sempre", "a partir de agora", "lembra"); a direct correction; rework (he asked again or undid the result); a
   tool error followed by a workaround that worked; a loaded skill proven wrong; an approach he explicitly praised
   (never infer approval from silence).
3. **Drop what must not be captured:** environment failures (missing binary, credential; capture the fix in a setup
   skill instead), negative claims about tools ("X is broken"), transient errors, one-off narration, unresolved
   failures. A one-off request is not a standing rule unless he marked it general.
4. **Shape each lesson** (at most 3 to 5 per retro):
   - **Home:** the skill that was in play, else an umbrella skill, else a `references/<topic>.md`, a new skill only
     at class level. A fact about the repo goes to its `$WIKI_HOME/<projeto>/`, never both places.
   - **Rule:** one imperative sentence plus one clause of why; no date, PR or narrative in the text that lands.
   - **Evidence:** the owner's quote (it lives in the event, not in the skill).
   - **Kind:** `skill_gap` (the skill lacked it) or `alignment_gap` (ambiguous instruction).
   - **Dedupe:** read the skill and its `references/`; `new`, `reinforce` (edit the existing sentence) or
     `already_covered` (drop it). Run `rejected-rules`: a rule rejected twice is not proposed again.
   - **Confidence:** `explicit` > `repeated` > `inferred`; inferred ones go only under a "talvez" group.
   `emit lesson.proposed '{"text": "...", "skill": "...", "rule": "...", "why": "...", "quote": "...", "kind": "...", "dedupe": "...", "confidence": "..."}' --lesson <id>`.
5. **Ask.** One multi-select with the harness's ask tool (Hermes `clarify` with `multi_select`, Claude Code
   `AskUserQuestion` with `multiSelect`); each choice reads `skill · regra`. Then `emit lesson.accepted` or
   `lesson.rejected '{"text": "...", "reason": "duplicada|errada|específica demais"}'` for each.
6. **Apply** the accepted ones with skill-smith: read the file before writing, fix the sentence in place, one lesson
   one rule, bump `metadata.version`, add a CHANGELOG entry. Work in a worktree
   (`wt switch -c retro/<date> --base origin/main --no-cd`), one PR for the whole retro. After the merge,
   `emit lesson.applied '{"text": "...", "pr": "<url>"}' --lesson <id>` and `wt remove`. Never delete a skill. If the
   skill is locked, return the suggested change in the report.
7. **Recurrence.** When a later retro finds the same correction for a skill that already has the rule, the rule is
   badly written or badly placed: `emit lesson.recurred` and propose a reinforcement (rewrite it or move it up),
   never a second copy.

Finish with a short report in Portuguese: lessons applied, rejected, and what stayed too fuzzy to encode.
