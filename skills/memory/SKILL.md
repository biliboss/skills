---
name: memory
description: Reduce an agent (all sessions of its folder) or one session to a small searchable memory (facts.jsonl) of decisions, preferences, corrections, durable facts and open requests, with the Devin SDK judging windows of the conversation and deterministic code validating every fact against its source. Use when the owner says "memory", "memória reduzida", "extrai a memória da sessão", "resume essa sessão em fatos", "processa as sessões do bot". Not wiki (curated project pages) and not memory-bot (talks to the Memory agent).
metadata:
  version: 0.2.0
---

# memory

```
bun run <skill dir>/scripts/memory.ts [<agent folder> | <session>] [options]
```

## Arguments

| Argument | Meaning |
|---|---|
| `<agent folder>` | The agent's folder: reads all its sessions in time order. The default is the current folder. |
| `<session>` | One session only: id, an unambiguous id prefix, or a path to the `.jsonl`. |

## Options

| Option | Default | Meaning |
|---|---|---|
| `--last N` | none | Only the last N owner messages and what follows them. Starts from an empty memory and overwrites `--out`. |
| `--out DIR` | `.memory/<scope>`, or `.memory/<scope>-last` with `--last` | Where the memory lives. Reuse the same folder to continue. |
| `--every N` | `MEMORY_EVERY` or `20` | Close a window every N owner messages. |
| `--model ID` | `MEMORY_MODEL` or `swe-2-high` | Model id advertised by the Devin session. |
| `--rules FILE` | none | The agent's current rules, usually its `AGENTS.md`. They outrank older facts. |
| `--limit N` | all | Process at most N windows in this run. |

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `DEVIN_BIN` | `devin` | The logged-in Devin CLI. No API key is used. |
| `MEMORY_EVERY` | `20` | Default for `--every`. |
| `MEMORY_MODEL` | `swe-2-high` | Default for `--model`. |

## Output

| Path | Content |
|---|---|
| `<out>/facts.jsonl` | The memory, one fact per line: `ts`, `type`, `title`, `fact`, `source`, `supersedes`. |
| `<out>/memory.json` | The cursor: how many messages are already absorbed. |
| `<out>/work/` | Files of the last window, for inspection. |

Stdout prints the path of `facts.jsonl`; progress goes to stderr. Exit code is `0` on success and `1` on any failure.

## Behaviour

- A run reads only what comes after the cursor, so run it again on the same `--out` after the session grows.
- Each window gets up to two repair turns. If violations remain, the run stops with exit `1` and keeps the last good memory.
- Messages after the last owner message wait for the next run.

## Examples

```
bun run scripts/memory.ts ~/agents/bili --last 10
bun run scripts/memory.ts ~/agents/bili --rules ~/agents/bili/AGENTS.md
bun run scripts/memory.ts 0879d991 --out ~/agents/bili/.memory/0879d991 --rules ~/agents/bili/AGENTS.md
bun run scripts/memory.ts ./session.jsonl --every 10 --limit 1
```

The extraction prompt is [resources/prompt.md](resources/prompt.md). The domain contract is [scripts/interface.ts](scripts/interface.ts).
