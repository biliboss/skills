---
name: brainstorm
description: >-
  A piece of `shape` (only by /brainstorm): when the idea is still open, think it through with the owner
  in a Double Diamond with systems thinking (Cynefin, iceberg, causal loops, leverage points), one question
  at a time, then a short design note for the backbrief. `shape` calls it; the agent does not pick it by
  itself.
disable-model-invocation: true
metadata:
  version: 0.2.1
  license: MIT
---

# brainstorm

Owner-facing text is Portuguese (Brazil). Credits for every base: [README.md](README.md#créditos-e-referências).
Depth on each tool: [references/tools.md](references/tools.md); what was borrowed: [references/prior-art.md](references/prior-art.md).

The journal is global, `~/.local/share/brainstorm/events.jsonl` (override `BRAINSTORM_DIR`); the only writer is
`scripts/brainstorm.sh emit`:

```
scripts/brainstorm.sh emit <event> '{"text": "..."}' --session <id> --actor <who>
scripts/brainstorm.sh sessions [--status S]
scripts/brainstorm.sh graph <session>        # the causal loop as JSON: nodes, edges (+/-), loops (R/B)
```

Events: `session.started|finished`, `problem.classified {domain}`, `question.asked|answered`, `variable.added {name}`,
`link.added {from,to,polarity}`, `loop.identified {kind R|B, variables}`, `approach.proposed|chosen`,
`leverage.ranked {level 1-12, text}`. Every event but the free-text ones is validated; a bad one exits 2.

## The dialogue (always)

1. **Ask first, one question at a time**, through the harness's ask tool (Hermes `clarify`, Claude Code
   `AskUserQuestion`); short, pt-BR, with 2-4 choices when the answers can be named. Read what the owner already
   gave (files, the conversation) before asking; never ask what it answers. A scope question (which part, which
   kind of content) carries a "Tudo, completo" choice: he usually wants the whole map, and narrowing choices alone
   cost a round.
2. **Propose 2-3 approaches** with their trade-offs and a recommendation, in a message of their own.
3. **Approve the design in sections**, each short, one confirmation per section.
4. Emit as you go (`session.started` with the owner's words first). Every emit needs `--session`, including the first:
   pick the id yourself (`bs-$(date +%s)`) and keep it in a scratch file for the later emits; batch the emits of one
   step (variables, links, loops, approaches) in one small `.sh`. A clear task is not a brainstorm: route to task-backbrief.
5. **A product brainstorm in this house maps the domain's events, all of them** (setup, triggers from the product's
   existing events, creation, the owner's decision, publishing, result back to the product's own events), as a table
   by stage: the owner thinks in event catalogues and asks for completeness, not a short list. Name each with the
   product's existing vocabulary, and tie the result to an event the product already emits (the lead, the visit).
6. Say legal and outward-facing limits inside the question, not after: an option that would be misleading advertising
   or publish without the owner's approval is named as such in the choice text.

## The frame: Double Diamond (diverge, converge, twice)

| Stage | Move | Tools that fit |
|---|---|---|
| Discover (diverge) | many questions and facts, no solutions | Cynefin, iceberg |
| Define (converge) | one problem statement | iceberg, causal loop |
| Develop (diverge) | several approaches | causal loop, leverage points |
| Deliver (converge) | pick one, write the note | leverage points |

## Systems thinking tools (each where it fits, never all every time)

- **Cynefin** (first): classify the problem, emit `problem.classified`. clear = apply the rule; complicated = analyse,
  then decide; complex = run a small experiment and sense; chaotic = act, then sense; disorder = split it up first.
  A complex problem gets an experiment as its approach, not a plan.
- **Iceberg** (discover/define): event, then pattern, then structure, then mental model. Ask "o que aconteceu, e o
  que se repete?" and go one level down until the answer is a structure or a belief, not a symptom.
- **Causal loop** (define/develop): variables as nouns that can rise or fall; each link has `+` (same direction) or
  `-` (opposite). Emit `variable.added` and `link.added`; a closed cycle with an even count of `-` is R (reinforcing),
  odd is B (balancing): emit `loop.identified`. Skip it when there is no feedback to see.
- **Leverage points** (develop): rank where to act with Meadows' 12 levels (Meadows' numbering: 12 = numbers, the
  weakest; 1 = transcending paradigms, the strongest and hardest). Emit `leverage.ranked`.

## Output: the design note

A short note, no template ceremony: the chosen approach and why, in the first person, "Decidi X porque Y", with
the rejected approaches in one line each. Emit `approach.chosen` with it. When the owner agrees, run
`session.finished` and hand the note to **task-backbrief** as the task to confirm. A decision about how the house works
(who does what, which tool owns a job) needs no backbrief: write it at once in the `.wiki` page that governs it, with
the session id as its source, and apply the small parts (a tab renamed, a window moved) in the same turn.

An unsure answer ("sei lá, acho que…") still names a use: restate the use it implies (a habit, a test bench, a
feeling of quality) and turn the doubt into something measurable in the recommendation, instead of asking again.

## The causal loop in the dev-console

The loop shows in the console as the Brainstorm domain (`scripts/dev_console_project.py`, widget `CausalLoop`: variables
as nodes, links as arrows labelled + or -, loops listed below). Add it with `console.sh domains add
<this skill>/scripts/dev_console_project.py`; it only reads the journal. Draw nothing by hand: emit the events.

## Pitfalls

- Do not brainstorm a clear task; two sentences of doubt are not a session. Route it to backbrief.
- One question per message; a list of questions gets one answer and loses the rest.
- Do not run every tool: pick by Cynefin domain. A chaotic problem needs action first, not a diagram.
- A link's polarity is about the variables, not about good or bad: `+` means they move the same way.
- Tests: `uv run --script scripts/test_brainstorm.py` (temp `BRAINSTORM_DIR`; never the real journal).
