# Prior art

Links answered HTTP 200 on 2026-11-06 (`curl -sIL`).

| Source | What it does | Idea taken |
|---|---|---|
| [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) | Names for spans and attributes of LLM calls and tool use | One trace per response, one span per resource, namespaced attributes (`trace.*`) |
| [OTLP specification](https://opentelemetry.io/docs/specs/otlp/) | The wire/JSON shape of traces | `--otlp` writes `resourceSpans` with `traceId`, `spanId`, `parentSpanId`, `attributes` |
| [OpenInference](https://github.com/Arize-ai/openinference) | OTel-compatible tracing conventions for LLM apps (retriever, tool, chain spans) | Typed spans (`tipo`) instead of a flat list |
| [Langfuse data model](https://langfuse.com/docs/observability/data-model) | Trace → observation hierarchy with metadata | A root trace with child observations, and metadata beside each |

Design choice of this skill: the transcript proves *what was loaded and called* (`observed`); *why it mattered*
(`efeito`, `peso`) is the agent's own account and is marked `inferred`, because a model cannot inspect its own
attention.
