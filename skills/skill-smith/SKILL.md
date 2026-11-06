---
name: skill-smith
description: Create, update or adapt an agent skill (SKILL.md) so the next session does the task right on the first try. CREATE turns a workflow from this session (or notes, or a fresh idea) into a skill; UPDATE folds a correction or lesson into every skill it affects, with a diff per file; ADAPT ports an external skill (GitHub, local disk, pasted) with a license check and attribution. Prefers patching an existing skill over making a new one. Use when the user says "skill-smith", "skillify", "make this a skill", "turn this into a skill", "update the X skill", "remember this in the skill", "propagate this lesson", "port/adapt this skill", or corrects how a class of task should be done.
metadata:
  version: 0.4.1
  license: MIT
---

# skill-smith — forge, temper and port skills

A skill is **the instructions for doing a class of task the most efficient and correct way, to this user's specifications**: the steps in order, the commands that work, the decision points, how the result should look, and the pitfalls that cost time. A future session must be able to follow it and get it right the first time. Everything below serves that.

Sources and credits: [ATTRIBUTION.md](ATTRIBUTION.md). Changes: [CHANGELOG.md](CHANGELOG.md). Its own memory: [.wiki/](.wiki/README.md).

## Step 0 — Read your own wiki, then pick the mode

1. `rg -n -i '<keyword>' <this skill's folder>/.wiki` (e.g. `~/.claude/skills/skill-smith/.wiki`) for lessons about running skill-smith itself (it is short; read only what matches).
2. Route by signal; if it is ambiguous, ask. Never guess between CREATE and ADAPT when an external URL is involved.

| Signal | Mode |
|---|---|
| A workflow was worked out in this session, or "make this a skill" | **CREATE** |
| A correction, validation, or "remember this" about a class of task; "update X skill" | **UPDATE** |
| A URL, path or pasted SKILL.md from someone else; "port / adapt / fork this skill" | **ADAPT** ([references/adapt.md](references/adapt.md)) |
| A one-line fix the user dictated, touching one skill | Just `Edit` it and bump PATCH. No ceremony. |

## Step 1 — The gate: is this worth a skill at all?

All three must be true ([skillify's quality gate](https://github.com/Yeachan-Heo/oh-my-claudecode/blob/0564555b63dfedd158669c6799d53743abd7d6bf/skills/skillify/SKILL.md)):

- Could someone find it with a 5-minute web search? **No.**
- Is it specific to this user, project or workflow? **Yes.**
- Did it take real debugging, design or operational effort to find out? **Yes.**

Do **not** capture ([Hermes `_DO_NOT_CAPTURE_BLOCK`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L422-L446)):

- **Environment failures** (missing binary, unset credential, "command not found"). Capture the *fix* under a setup skill, never "X does not work".
- **Negative claims about tools** ("browser tools are broken"). They harden into refusals long after the cause is fixed.
- **Transient errors** that went away on retry. If anything, the lesson is the retry.
- **One-off tasks** ("summarize this PR") that are not a class of work.
- **Unresolved failures.** If the session never found a working method, do not write the dead ends up as a recommended workflow. Say "nothing to save".

Where a lesson belongs:

| The lesson is… | It goes to |
|---|---|
| How to do a class of task (steps, pitfalls, format preferences) | a skill |
| Who the user is, or the current state of things | memory / `CLAUDE.md` |
| How this repo works, for everyone | the repo's `.wiki/` (or `AGENTS.md`), not a skill |
| Both a principle and a skill rule | both; write each once |

## Step 1b — Research the open source first (CREATE, ADAPT, any MINOR+ UPDATE)

The owner's rule: no skill is written from a blank page. Before drafting, spend a short, bounded pass (~10 min, a
subagent when the harness has one) on how others already solved the class of task, and steal the best ideas:

1. **Hermes Agent**, the house's reference: its own loop and skills (`agent/background_review.py`, the bundled and hub
   skills: `hermes skills search <topic>`; the local install under `~/.hermes/hermes-agent/`).
2. **GitHub**: `gh search repos "<topic> skill"`, `gh search code "<topic>" --filename SKILL.md`, Claude Code plugins
   and marketplaces, Anthropic's [skills](https://github.com/anthropics/skills), the [Agent Skills spec](https://agentskills.io/specification).
3. **The literature's name** for the practice (a paper, a field's term), so the skill uses it instead of inventing one.

Write what you kept in `references/prior-art.md` (one line per source: what it does, the idea taken, the link) and
credit adapted text in `ATTRIBUTION.md`. A one-line PATCH dictated by the owner skips this step.

## Step 2 — Find the home: patch before you create

Take the **first** option that fits ([Hermes' preference order](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L469-L497)):

1. **A skill that was loaded this session** and covers the lesson. It was in play, so extend it.
2. **An existing broad skill** for the class of task. Find it with `rg -l -i '<terms>' .claude/skills ~/.claude/skills --glob 'SKILL.md'`, then read it.
3. **A support file** under an existing skill: `references/<topic>.md` (depth needed only sometimes), `templates/` (files to copy), `scripts/` (re-runnable actions). Add a one-line pointer in its SKILL.md.
4. **A new class-level skill**, only when nothing above covers the class. Name it for the class (`deploy-vps`), not the incident (`fix-tuesday-deploy`). Check the name against the harnesses' built-in slash commands (Claude Code, Hermes, pi) before creating it: a skill named like a built-in (`tasks` vs Claude Code's `/tasks`) loses its short command and gets a fallback such as `/skill tasks`. A workflow over a domain is one skill named `<entity>-<action>`, or, when the practice has its own short name in the literature, that name (`backbrief`, `retro`), since short names are preferred: one command runs the whole workflow, never one skill per command (they would each repeat the contract and the journal); the domain itself keeps its plural name.

**Read before you write.** Open the current SKILL.md (and any file you will overwrite) in this session before editing it. Hermes [enforces this in code](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/skill_manager_guards.py); here it is a rule.

Location:

| Scope | Path |
|---|---|
| This repo, everyone | `<repo>/.claude/skills/<name>/` |
| This user, every project | a skill of one of our plugins (`biliboss/skills` public, `biliboss/skills-casa` private): `skills/<name>/` plus its path in `.claude-plugin/plugin.json`; otherwise `~/.claude/skills/<name>/` |
| A Hermes agent | `~/.hermes/skills/[category/]<name>/` |
| A kind of skill that already has its own maker (e.g. a `database-skill-creator`) | not here: use that maker |

## Step 3 — Write it well

Rules for the content ([Hermes `_LESSON_LAYER_BLOCK`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L390-L420)):

- **Steps first**, in the order they are done, with concrete commands and decision points. Each pitfall sits on the step it affects.
- **A pitfall is a rule plus one clause of why**, in the imperative: "Grep the tests for the symbol before widening a signature — hand-rolled mocks copy the old shape and fail on a shard you did not run."
- **No incident narration**: no PR numbers, dates, ticket IDs or quoted chat as content. The rule must stand without the story.
- **One lesson, one rule.** Search the skill for the rule first; strengthen it instead of appending a second copy.
- **Fix in place.** Edit the sentence that misled; never append "UPDATE: actually…".
- **Don't restate the environment**: what `AGENTS.md`, `CLAUDE.md` or a tool's own description already teach.
- **Actions are `.sh` scripts in `scripts/`, not an MCP server** (the user's preference): a script is faster to iterate, runs from any shell or agent, and is read before it is run. The `.sh` is the interface every harness calls; heavier logic lives behind it in a `uv` PEP 723 script or `jq`. Reach for an MCP only when the action needs a long-lived connection or state that a script cannot keep.
- **A skill that ships an app or widget keeps the app a read-only view; the agent is the engine** (the user's design rule): the skill's script is the only writer of a state file (atomic temp + `mv`), the app watches it (kqueue/file events, no polling) and never writes, and the app has no menus, presets or buttons of its own. Options in the UI duplicate what the agent decides and split the state between two writers.
- **Always-on rules live in SKILL.md** (aim for under ~200 lines). `references/` holds topical depth, one file per topic, never `<date>-<incident>.md`.

Frontmatter (format per the [Agent Skills spec](https://agentskills.io/specification) and [Claude Code skills docs](https://docs.claude.com/en/docs/claude-code/skills)):

```yaml
---
name: <kebab-case, the class of task>
description: <what it does + when to use it, with 4–8 trigger phrases in quotes; say how it differs from nearby skills; under ~1000 chars>
metadata:
  version: 0.1.0
---
```

The description is what routes the skill. Lead with the task, list the phrases a user actually says, and name the neighbour it should *not* be confused with. Keep it under 1024 characters and free of a bare `: ` (write `;` or quote the whole value) — pi rejects both as invalid frontmatter, while Claude Code silently accepts them.

Every skill skill-smith creates has its own `README.md` and `CHANGELOG.md`, side by side with `SKILL.md`:

- **`SKILL.md`** is the agent's instructions and the only place a rule is written.
- **`README.md`** is the human page: what the skill is, how it works in a few steps, the scripts or commands in a table with one example each, how to run its tests, and a link to the CHANGELOG. It points to SKILL.md for the rules and does not restate them, so the two never diverge.
- **`CHANGELOG.md`** ([Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)) is the history, starting at `## [0.1.0] - <today>`.

Ship a minimal v0.1.0: SKILL.md, the README, the CHANGELOG, and at most one or two references. Iterate after real use. A skill you update (step 4) gets the README too when it lacks one; do not backfill the skills you are not touching.

## Step 4 — UPDATE: one lesson, every skill it touches

([skillify-pro UPDATE mode](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/skills/skillify/SKILL.md#mode-update))

1. **List the learnings**, one change each. Signals: corrections ("stop doing X"), validations ("yes, do that again" — lock it in), a new pattern, a style or format preference, a tool switch, a gap the skill should have covered.
2. **Find every affected skill**: keyword `rg` over all skill dirs, then a judgment pass. Sort by confidence: **high** (propose the change), **medium** (ask explicitly), **low** (mention only).
3. **Show a diff per file**: before, after, a one-line why, and the version bump. Get approval per file, not as one bundle.
4. **Apply**, bump `metadata.version` once per skill, add a CHANGELOG entry, and create the skill's `README.md` if it has none (step 3 says what goes in it).

## Step 5 — Version and changelog

[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html), per skill:

| Bump | When |
|---|---|
| PATCH | Clarification, wording, a new pitfall that doesn't change the flow |
| MINOR | A new step, mode, option or reference file; new behaviour that is backward compatible |
| MAJOR | Rename, removed mode, changed output; in 0.x a MINOR may carry it |

Don't bump for a typo. Every bump gets a dated entry under `Added / Changed / Fixed / Removed`.

## Step 6 — Check, then hand over

1. **Lint by eye**: frontmatter parses; `name` matches the folder; links resolve; no incident narration; SKILL.md has no rule written twice. The skill folder has a `README.md` and a `CHANGELOG.md`, the CHANGELOG's top entry matches `metadata.version`, and the README links to the CHANGELOG and does not restate SKILL.md's rules.
2. **Test when it matters** (a new skill, or a MINOR+ change): run 2–3 realistic prompts as a fresh subagent with only the skill, and see if it does the task right. For deeper evals and description tuning, use Anthropic's [skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) (`anthropic-skills:skill-creator`).
3. **Commit only your own files, by path**, never `git add -A`. Don't push or open a PR unless the user asks. Adding a whole skill folder also picks up whatever a run left there: read `git diff --cached --stat` before committing and unstage secrets (FastHTML's `.sesskey`, `.env`) and files another session created; gitignore the secret. When another session also edited a file you touched (shared checkout), stage only your hunks: build the blob from `git show HEAD:<file>` plus your edits and `git update-index --cacheinfo 100644,$(git hash-object -w <blob>),<file>`; the other session's lines stay uncommitted in the working tree.
4. **Install it where it runs** (after the push, for a plugin skill): bump `version` in `.claude-plugin/plugin.json` (and the root CHANGELOG) whenever a skill is added or renamed — `claude plugin update` compares that version and answers "already at the latest" otherwise; then `claude plugin marketplace update <marketplace>` and `claude plugin update <plugin>@<marketplace>`; Hermes reads the clone through `skills.external_dirs`, so keep the clone on `main` (a stale branch hides new skills) and verify with `hermes -p <profile> skills list`; for pi, the `pi` skill's `ligar-skills.sh` links every plugin skill into `~/.pi/agent/skills`. Sessions already open keep the old copy: tell the user to run `/reload-plugins` (Claude Code) or `/reload` (pi).
   - **Two open PRs that both bump `plugin.json`:** give the second the next version from the start (one PR takes 0.N.0, the other 0.N+1.0) and merge them in that order. After the first merges, bring `origin/main` into the second branch with `git merge`, not a rebase — `gh-app` refuses force pushes, so a rebased branch cannot be pushed. Resolve `plugin.json` by keeping main's description (it carries the other skill's mention) and setting the higher version; in the root CHANGELOG put the newer block above the older one; rerun the skill's tests before merging.
5. **Report**: the learnings, the skills touched with their versions, and anything flagged but skipped. Point out what is still too fuzzy to encode.

## Step 7 — Keep your own wiki

skill-smith keeps a small memory of how to run itself, in [.wiki/](.wiki/README.md).

**Edit the source, not the installed copy.** skill-smith ships in the `biliboss-skills` plugin; the installed copy in the plugin cache is overwritten on every update. Write lessons and changes in a clone of [biliboss/skills](https://github.com/biliboss/skills) (`skills/skill-smith/`), commit and push them, and update: `claude plugin update biliboss-skills@biliboss`. Without the source, edit the installed copy and say so in the report.

- If this run taught something about *forging skills* (a routing mistake, a gate that misfired, a user preference about skill format), add one line to [.wiki/lessons.md](.wiki/lessons.md): `- YYYY-MM-DD — <rule + why>`.
- When the same lesson shows up twice, or it changes the procedure, promote it: patch this SKILL.md, bump the version, add a CHANGELOG entry, and mark the lesson line `→ promoted in x.y.z`.
- Decisions about skill-smith's own design go in [.wiki/design.md](.wiki/design.md).
