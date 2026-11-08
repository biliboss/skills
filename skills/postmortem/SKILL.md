---
name: postmortem
description: Go from a reported problem back to the decision that caused it, rebuilt from the agent event stream (NATS JetStream), then write a blameless postmortem and apply the fix as a wiki rule or skill patch. Use when the user says "postmortem", "post-mortem", "what happened", "why did the agent do that", "o que aconteceu", "por que fez isso", "reconstrói a decisão", "isso deu errado" or reports a wrong result from an agent turn. Not systematic-debugging (that debugs code); this debugs an agent decision from its events.
metadata:
  version: 0.1.0
  license: MIT
---

# postmortem — from a reported problem to the decision behind it

Principle: errors are **understood from the events, not prevented by review**. When a problem is reported, rebuild the decision that led to it (the request, what was read, the tools called, what was decided and why) and answer three things: **what happened, why, what changes** so it does not repeat. The change is a rule or a skill patch, never a promise.

## Why this name, and the sources

- **postmortem**: Google SRE, [Postmortem Culture: Learning from Failure](https://sre.google/sre-book/postmortem-culture/). Blameless: name causes in the system (a vague request, a missing rule, a tool default), never a culprit.
- **The record model**: [W3C PROV-O](https://www.w3.org/TR/prov-o/). Activity (an event/turn/tool call), Entity (what was read or produced), Agent (who acted); `used`, `wasGeneratedBy`, `wasAssociatedWith`. `timeline.py --json` emits this shape.
- **The trace**: [OpenTelemetry GenAI agent spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md): `invoke_agent`, `execute_tool`, `gen_ai.conversation.id`. A turn is the invoke, tool events are the executes, the trace/conversation id ties them.

## Config (env, no defaults tied to a house)

`NATS_URL` (default `nats://127.0.0.1:4222`), `POSTMORTEM_STREAM` (default: found by subject), `POSTMORTEM_SUBJECT_PREFIX` (e.g. `mesa`; default all subjects). Grammar: `<prefix>.<domain>.<entity>.<event>` (`request`, `turn`, `tool`, `subagent`, `decision.made`, logs). Payloads are JSON; the script reads `turn_id`, `trace_id`, `actor`, `ts` when present. The stream is **read-only** here: never publish, purge or edit it.

## Procedure

1. **Window and anchor.** Get from the report the card (or request text), the turn or trace, and a rough time. Start wide (`--since 2h`), narrow after. If there is no id, find the request event by a word from the report: `scripts/timeline.sh --since 2h | rg -i '<word>'`.
2. **Pull the events.**
   `scripts/timeline.sh --card <CARD> --since <ISO|2h> [--until <ISO>]` (or `--turn`, `--trace`). One line per event: time, subject, actor, short fields, grouped by turn. A card pulls every turn and trace it touches. Exit 1 = nothing matched: widen the window or fix the id. For a full record use `--json` (PROV-like: activities, entities used/generated, agents). Pull the full payload of the key events (`nats stream view`/`nats sub --start-time`, read-only) when a field is cut short.
3. **Build the chain** request → read → tool calls → decision → effect. For each link say which event proves it (seq/time). Mark gaps ("no `decision.made` for this turn", "file read after the write") as findings, not guesses. Check the decision's `why` against the request: did the agent read what the user asked?
4. **Write the postmortem** from [references/postmortem.md](references/postmortem.md): what happened, why, contributing causes (several; rarely one), what changes. Blameless, evidence-cited, short.
5. **Apply the change** before closing: a rule in the repo wiki (wiki) or a patch to the skill that was in play (skill-smith UPDATE), committed. A "next time I will…" with no file changed is not a result. Report the path of what changed.

## Pitfalls

- Reconstruct from events only; do not re-run the failing action to "see" it, it may repeat the damage.
- A missing event is evidence about instrumentation, not proof the step did not happen: say which, and propose emitting it.
- Event times are shown in the local zone; pass `--since/--until` in ISO with `Z` to avoid off-by-hours windows.
- Do not stop at the proximate cause ("the agent ran `rm`"); ask why the request or rules made that the reasonable choice.
