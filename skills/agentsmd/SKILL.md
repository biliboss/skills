---
name: agentsmd
description: >-
  Create, migrate or audit a project's AGENTS.md and agent memory with the best practices of agents.md and of real
  repositories. Keeps always-loaded rules short and stable, and moves what ages (status, scores, open PRs, history)
  to a STATE.md where each claim has a source and a verification date. Use when the user says "agentsmd", "cria o
  AGENTS.md", "create an AGENTS.md", "organiza a memória do projeto", "junta as memórias", "audita o AGENTS.md",
  "AGENTS.md is too long" or "memória desatualizada". Not `wiki-smith` (the long-form wiki), not `memory` (reduces a
  session to facts.jsonl), not `skill-smith` (a class of task, not a project).
metadata:
  version: 0.2.0
  license: MIT
---

# agentsmd

An AGENTS.md is paid for in every session, so each line must change what an agent does. Memory that ages does harm
there: an agent reads an old status as a current fact.

Copy from [templates/AGENTS.md](templates/AGENTS.md) and [templates/STATE.md](templates/STATE.md). Sources:
[references/prior-art.md](references/prior-art.md).

## Pick the mode

| Signal | Mode |
|---|---|
| The project has no AGENTS.md | CREATE |
| Memory is scattered across wikis, issues, notes or old sessions | MIGRATE |
| An AGENTS.md exists and is long, contradictory or stale | AUDIT |

## Where each thing goes

Sort every candidate line by this table before writing it.

| The line is | It goes to |
|---|---|
| A rule the agent cannot infer, a command, a boundary, a pitfall | `AGENTS.md` |
| Rule that holds only in one package or directory | the nearest nested `AGENTS.md` |
| Status, score, open PR, deploy state, pending decision | `STATE.md` |
| Why a decision was made | an ADR, issue or wiki page; link it from `AGENTS.md` only if it constrains future work |
| History, incident stories, finished work | the issue tracker or git; nowhere in memory |
| A step-by-step task used only sometimes | a skill or a doc, linked by one line |
| What the agent finds by reading the code (tree, stack, generic overview) | nowhere |
| Secret values | nowhere; name the vault and the variable |
| Personal preference, per-machine path | global or local memory, not the versioned file |

## CREATE

1. Read the README, the build manifests and CI. CI shows which commands really gate a change.
2. Run each command you plan to list, or mark it `(not run)`. A wrong command costs more than a missing one.
3. Fill the template by hand, one line at a time. Delete every empty section; do not leave placeholders. Do not paste
   a generated overview, since generic overviews add cost without helping.
4. Keep `AGENTS.md` under 200 lines. Past that, move path-specific rules to nested files; an `@import` does not save
   context, it only reorganizes it.
5. Create `CLAUDE.md` with the single line `@AGENTS.md`. Claude Code skips AGENTS.md when a CLAUDE.md exists unless it
   imports it. Inside a parent folder of shared rules, also import the parent (`@../AGENTS.md`).
6. Check the import loaded: start a fresh session and ask it to quote one rule from the file.

## MIGRATE

1. List every source: wikis, notes, issues, tracker, code, deployed system. Use parallel subagents when it is large,
   one source each, and require a path or URL on every claim, marking fact versus inference. For past
   sessions of an agent, run the `memory` skill on its folder and treat `facts.jsonl` as one more source: each fact's
   `source` is its origin, and status facts still go through step 3.
2. Rank the sources for each kind of fact. Live system and forge beat notes; the code on the default branch beats a
   local checkout, which may be behind; the newest dated note beats older notes.
3. Verify every status claim at its primary source before copying it (`gh pr view`, the health endpoint, `git log`
   on the remote ref). Notes commonly disagree with the forge about whether a PR is merged.
4. Sort each surviving item with the table above. A fact lives in one place; others link to it.
5. Record what could not be verified in `STATE.md` under "Unverified", and contradictions you could not settle under
   "Conflicts". Never pick a winner silently.
6. Never copy secret values, and keep the output private when it names clients, hosts or people.

## AUDIT

Report before changing, one finding per line with the file and line:

- Over 200 lines, or over 32 KiB across the chain from root to working directory (Codex stops adding there).
- State inside rules: dates, scores, PR numbers, "today", "currently", "last work".
- A fact repeated in more than one file, or two rules that contradict each other; an agent may pick either.
- A command that does not run, a path that does not exist, a link that is broken.
- An import that the text claims but the file does not have.
- Lines the agent could learn by reading the code.
- Copied configuration values that will drift from their source, such as account ids.

## How to write a rule

- One line, imperative, with the reason: "Workers never touch the metadata DB; each task holds a scoped token."
- Say what to do on failure: "If the lab cannot start, stop and report which call failed. Do not build a substitute."
- A rule that may be broken declares its exit: "Start the watcher unless it is running; if you skip it, say why."
- Define what counts as evidence: "A test that fails on a typo or a bad import does not count as red."
- A pitfall gives the exact sequence: "`make verify` compares against HEAD, so commit first."
- Map change to command: "Changed only `api/` → `pnpm test:api`."
- Point at the source instead of copying it: a Makefile target beats a pasted command list.

## Keeping STATE.md honest

- `STATE.md` is not imported: it is read when the task depends on it, so its cost is paid only then.
- Each claim carries `(source, verified YYYY-MM-DD)`. A claim with no source is not state.
- Before acting on a claim, check its age. Past the file's `stale_after`, re-verify at the source first.
- Correct the claim in place. Do not append a newer version beside it, and remove what is finished.
- Facts another system holds (issue status, PR state) are linked and re-read, not transcribed, unless the transcription
  is the point of the snapshot.

## Finish

1. Run the AUDIT list against what you wrote.
2. Report what went where, what stayed unverified, and which decisions only the owner can make.
