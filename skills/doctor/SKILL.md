---
name: doctor
description: >-
  Use when taking over a project (especially an unknown one), when the owner says "doctor", "roda o doctor", "is it
  healthy", "está saudável?", or when adding a health diagnosis to a project or tool. Every project gets a doctor():
  five dimensions (environment, architecture, behavior, observability, agent), read-only findings with the exact fix.
  The doctor is also the only behaviour check: smokes and critical rules in the project doctor, no test suite.
metadata:
  version: 0.2.0
  license: MIT
---

# doctor — "is the system healthy and ready to work?"

Every project and tool gets a `doctor` method. **`doctor()` asks whether the system is healthy, ready to work, and
behaving as it must.** There is no test suite: behaviour is proven by smokes and critical-rule checks in the project's
own doctor, dimension `behavior`.
The owner calls this *doctor driven development*: a faster loop for an agent than starting from unit tests, because
the doctor also tells the agent whether it can work here at all.

## The rule

**First action on a project: run its doctor.** On an unknown project, if it has none, run the generic one
(`scripts/doctor.py <repo>`) and **propose** a project doctor from what it found. Run it again after each change
that could break the setup, and as a periodic check. Thread skill's `thread.sh doctor` is the first tool that follows
this protocol.

## The protocol

Five dimensions. A doctor diagnoses the software **and the agent's own ability to work in it**.

| Dimension | Asks | Typical checks |
|---|---|---|
| `environment` | Can I run it? | toolchain on PATH, dependencies installed, lock in sync, services up |
| `architecture` | Do I understand how it works? | entry points, components and invariants written down (README, `.wiki/`, `AGENTS.md`) |
| `behavior` | Is current behaviour right? | smokes of the real flow and critical-rule checks, written in the project doctor |
| `observability` | Would I notice a failure? | logs, events, health endpoints, a heartbeat |
| `agent` | Can this agent work here? | required CLIs, auth present **without reading secret values**, skills/wiki pages it needs, permissions, remote reachable |

**Finding** = `{dimension, check, status, evidence, action}`:

- `status`: `ok` · `warn` (works, but watch/improve) · `drift` (reality no longer matches what is declared: stale lock,
  doc vs code) · `fail` (cannot work).
- `evidence`: the raw fact seen (a path, an exit code, a count), never an opinion.
- `action`: the exact command or step that fixes it. **The doctor never runs it.**

Output:

- Text, one line per finding: `<status> <dimension> <check>: <evidence> -> <action>`
- `--json`: one JSON object per finding, per line (summary goes to stderr).
- `ok` findings only with `--verbose`; always a summary line.
- Exit `0` healthy (ok/warn only) · `1` drift or fail present · `2` the doctor itself could not run.
- **Read-only by default.** Repair is a separate, explicit step; a `--fix` exists only if the tool's owner adds it,
  and is never silent. Secrets: check presence by name, never print or read a value.

## Running the generic doctor

```bash
scripts/doctor.py <repo>                 # read-only; default .
scripts/doctor.py <repo> --gate          # end of a batch: no verified behavior finding is a fail (exit 1)
scripts/doctor.py <repo> --json --verbose
```

It detects the stack by files (pyproject/uv.lock, package.json, go.mod, justfile, Dockerfile), checks the tools are on
PATH, looks for README/`.wiki`/`docs`/`AGENTS.md`/`CLAUDE.md` and entry points, greps cheaply for logging/health/NATS, checks `git ls-remote` (timeout), `gh auth status` and write permission,
and compares `.env.example` names against the environment. It **discovers the project's own doctor** (`just doctor`,
`scripts/doctor*`, `<cli> doctor`), runs it and merges its findings (prefixed with where they came from).

The generic doctor knows nothing about what a project must do, so `behavior` comes only from the project doctor: a
finding `ok` there is the verified one. Without it the check `behavior smoke` is `warn`, and `fail` with `--gate`. A
`warn` from the project doctor does not count as verified, because `warn` is also how a skipped check is reported.
A smoke must be fast and read-only, like every other check.

## Adding a doctor to a project

Where it lives, in this order:

1. The project has a `justfile` → a `doctor` recipe. **Justfiles belong to T01: propose the recipe in the report or
   PR description, do not edit the justfile yourself.**
2. No justfile, a CLI exists → a `doctor` subcommand of that CLI.
3. Otherwise → an executable `scripts/doctor` (uv script, PEP 723, stdlib only).

Contract for any of them: print findings in the text format above (or `--json`), honour the exit codes, stay
read-only, and cover what is specific to the project: its services, queues, data files, credentials by name, the
invariants from its wiki, and in `behavior` a smoke of the real flow plus one check per critical rule. Do not repeat the generic checks; the generic doctor already runs them and merges yours.
Start from the generic doctor's warnings: each one is a missing piece to either fix or check on purpose.

## Pitfalls

- **The drift you already know is the doctor's acceptance test.** Before writing a doctor, list the real drift seen
  by hand (live state, read-only) and do not fix it; ship the doctor only when its run on the live system reports
  exactly those findings. Fixing first leaves the doctor untested against reality.
- **One exit-code scale across the house** (0 healthy incl. warn · 1 drift/fail · 2 could not run). A wiki page,
  README or project doctor stating another scale is itself drift: correct it to this one, do not add a variant.
- **A finding found while listing is still a finding.** When asked to list or report on a system that has a doctor
  (e.g. "list open threads"), run the doctor too and report drift next to the list.

- A doctor that "fixes" quietly hides the drift it found. Print the action; let the owner or the agent run it.
- `ok` for something not actually looked at is worse than `warn`. If a check was skipped, say so with `warn`.
- A missing optional thing (health endpoint in a CLI) is `warn` with the action to add it or to record why not.
- Never give the doctor network or secret access beyond reachability and presence-by-name.

Origins and credits: [README.md](README.md#créditos-e-referências).
