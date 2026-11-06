---
name: trace
description: >-
  Use when the owner asks why the last response was made, which of his own resources shaped it, or for a "trace"
  of the turn. Triggers "trace", "/trace", "por que você respondeu assim", "o que você usou", "trace da
  resposta", "quais skills e CLAUDE.md pesaram". Prints an OpenTelemetry-style trace of the last response with only
  what the owner authored (CLAUDE.md, AGENTS.md, .wiki pages, his skills, hooks, memory, settings); never the
  system prompt, built-in tools, MCPs or anthropic-skills. Differs from retro (lessons from corrections, writes
  rules) and postmortem (one error, read from NATS events): this one only explains a turn.
metadata:
  version: 0.1.0
---

# trace

The text for the owner is in Portuguese (Brazil). Read-only: the skill never writes to the transcript, the wiki
or any skill. Sources and the design reasoning: [references/prior-art.md](references/prior-art.md); human page: [README.md](README.md).

```
scripts/trace.sh [session.jsonl] [--back N] [--json] [--otlp FILE]
```

## Steps

1. **Collect the observed spans.** Run `scripts/trace.sh` with no argument (newest transcript of this folder;
   pass the path when the owner names another session). `--back 2` explains the response before the last. The
   script skips the turn that invoked this skill itself and slash-command echoes (`/model`).
2. **Fill `efeito` and `peso` for each span, yourself.** Re-read the turn you are explaining and, per resource,
   write one sentence: which line of it changed what you did, and how (`efeito`). Then `peso`: `decisivo`
   (the answer would differ without it), `contribuiu`, or `sem efeito`. These two fields are your interpretation,
   so mark them `inferred`; `observed` stays only for what the transcript proves (the file was loaded, the skill
   was called). If you cannot name the line, write `sem efeito`; never invent an influence to fill the tree.
3. **Add what the script cannot see.** A resource you used from memory of an earlier turn, or a rule from a file
   in context that matched, is an `inferred` span; add it with its path.
4. **Print the trace** in this shape, then a one-line `resumo` (how many resources, which one was decisive, how
   many had no effect):

```
trace  <session8>  "<prompt>"
├─ [claude_md] ~/biliboss/AGENTS.md  (ctx, observed)
│     efeito (inferred): manda ler o wiki antes de agir → li o index primeiro   peso: decisivo
└─ [skill] biliboss-skills:skill-smith  (skill, observed)
      efeito (inferred): ...   peso: contribuiu
resumo: 2 recursos seus, 1 decisivo, 0 sem efeito
```

5. **`--otlp FILE` only on request.** It writes the same spans as OTLP/JSON (`resourceSpans`, one root span
   `resposta` and a child per resource, `traceId` from the session). Put the file in the session scratchpad, not
   in a shared folder.

## Rules

- **Only the owner's resources.** Kept: `~/.claude/**`, `AGENTS.md`, `CLAUDE.md`, `.wiki/**`, `SKILL.md`, memory,
  `settings*.json`, plugin manifests, hooks. Dropped: `anthropic-skills:*`, built-in tools, MCP servers, the system
  prompt. Add a prefix to `NOT_OWNER_SKILLS` in the script when a plugin that is not his shows up.
- **The first skill listing is not usage.** Skills only appear when called with `Skill` (or read); the listing the
  harness injects is context, not a resource that shaped the answer.
- **The honest limit.** The transcript proves what was loaded and called, not what weighed in the answer; say so in
  one line when every `peso` is `inferred`.
