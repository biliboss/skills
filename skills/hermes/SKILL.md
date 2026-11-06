---
name: hermes
description: Drive the owner's local Hermes profiles (researcher, designer, sre, via-ads, mantainer, bili) as agents with their own model, SOUL, skills and persistent memory, from Claude Code or pi, through scripts/hermes.sh (list, spawn, resume, sessions, read, memory, route, dm). Use when the owner says "hermes", "ask the researcher", "have the designer/sre/via-ads/mantainer do it", "spawn a profile", "what does researcher remember", or a task has an owning profile (research, UI, infra, search and ads, machine upkeep). Not the `bili` skill, which is the VPS Bili through Linear; not for code with a PR (a worktree with a subagent).
metadata:
  version: 0.2.0
  license: MIT
---

# hermes — local Hermes profiles as agents with memory

A Hermes **profile** is an agent with its own model, SOUL.md, skills, cron, bots and **persistent curated memory**
(`memories/MEMORY.md`, `USER.md`). A Claude Code native subagent starts clean and dies with the session; a profile
remembers what it already researched or decided. Use a profile when the subject has an owner with history; use a
native subagent for code in a worktree. Sibling: [`bili`](../bili/SKILL.md) talks to the Bili on the VPS through
Linear and never directly; this skill talks to profiles on this machine and does not absorb it.

All actions go through `scripts/hermes.sh` (thin over the `hermes` CLI; logic in `hermes.py`). Run it by path from
this skill's folder. Rules and routing below; depth in [references/routing.md](references/routing.md).

## Steps

1. **Pick the profile.** `scripts/hermes.sh route <kind>` prints the owner (research, ui, infra, search, ads, disk,
   coordination). No owner, or code that ends in a PR: do not use a profile (backbrief step 9 native subagent). `list [--json]` shows each
   profile's model, description and whether it is allowed.
2. **Read what it already knows when it matters.** `scripts/hermes.sh memory <profile>` (read only).
3. **Run it.** `scripts/hermes.sh spawn <profile> "<task>" [--cwd DIR] [--timeout S]`. The profile sees nothing of
   this session: put the whole task, the constraints and the learnings in the prompt, no credentials. The output is
   the answer, then a last JSON line `{profile, session_id, exit_code, duration_s, usage}`.
4. **Check the exit code; only 0 is success.** 1 no text, 2 partial or failed, 130 interrupted, 124 timeout, 3 profile
   busy, 4 profile refused, 5 unknown profile. Report non-zero as it is; never present a partial as done.
5. **Follow up.** `resume <profile> <session> "<msg>"` continues a session; `sessions <profile> [--limit N]` lists;
   `read <profile> <session>` prints a trimmed export.
6. **Verify with other eyes.** The profile that did the work never verifies it (backbrief step 10 runs a fresh context).

## Rules

- **Flat plans only.** The script refuses a profile whose model provider is per-token (openrouter, an Anthropic API key);
  allowed: `claude-subscription*`, `zai*` coding plan, `openai-codex`. Do not bypass with `-m/--provider`.
- **Never two writers on one profile.** Two agent processes on one profile both write its memory and sessions. `spawn`
  and `resume` take a per-profile lock (`${HERMES_SKILL_STATE:-~/.local/state/hermes-skill}/locks/<profile>`) and
  exit 3 if it is held: wait or pick another profile, never delete the lock. A profile **open in a TUI or Desktop is a
  writer too** and the lock cannot see it: the script warns when it spots one; ask the owner to close it first.
- **Bot Chat is untouched.** Each profile's canonical `Bot Chat` belongs to the owner. `spawn` opens a fresh
  session. `dm <target> "<msg>" --owner-asked` goes through `hermes peer dm` and **only when the owner asked for it**.
- **Never print secrets.** No env dumps, no `.env`, no `config.yaml` beyond what the script shows; the usage JSON is
  filtered of key-like fields.
- **Proposals stay proposals.** `sre` and `via-ads` read, measure and propose; production, DNS, budget and indexing
  changes need the owner's go-ahead, so say so in the prompt.
- **Check the profile's SOUL before routing to it.** A profile whose SOUL.md is a stub or a copy of another's (designer
  once matched bili's; mantainer has no scope) does not own the subject yet: tell the owner, then spawn.
- Whether a `-z` run writes the profile's memory is **unverified**; try it on a throwaway profile before promising it.

## Claude Code mods (later)

A Claude Code mod could add a profile panel or a `/hermes` command through `$.process.spawn`. Routing the native
`agent.spawn` to Hermes is **unconfirmed**: the docs only say the hook may rewrite a spawned agent, not replace it
with an external process (research in `references/routing.md`). Not built; scripts cover the use today.

Tests: `python3 scripts/test_hermes.py` (fake `hermes` through `HERMES_BIN`, no model call). History: [CHANGELOG.md](CHANGELOG.md).
