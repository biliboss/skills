# Design decisions

Why skill-smith is shaped the way it is. Add a section when a decision changes; edit the old one in place and say what replaced it.

## One skill, three modes (0.1.0)

CREATE, UPDATE and ADAPT live in one skill so they share one gate, one set of content rules and one version policy. This follows [skillify-pro](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/skills/skillify/SKILL.md), which merged three separate skills for the same reason. ADAPT is used rarely, so its detail sits in [references/adapt.md](../references/adapt.md).

## Patch before create (0.1.0)

The usual way a skill library goes wrong is many narrow skills, one per session. [Hermes](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L469-L497) prevents this by trying, in order: the loaded skill, then an existing broad skill, then a support file, and only then a new skill. skill-smith uses the same order. [skillify (OMC)](https://github.com/Yeachan-Heo/oh-my-claudecode/blob/0564555b63dfedd158669c6799d53743abd7d6bf/skills/skillify/SKILL.md) can only create, which is the gap this closes.

## Rules, not stories (0.1.0)

A skill holds rules plus one clause of why, never narration of what happened. That is [Hermes' `_LESSON_LAYER_BLOCK`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L390-L420). Its [linter](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/skill_linter.py) flags incident numbers for the same reason. skill-smith checks this by eye at Step 6; it has no linter yet.

## Manual, with approval (0.1.0)

Hermes reviews in the background every 10 turns ([`creation_nudge_interval`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/agent_init.py#L1388-L1390)) and writes without asking. In Claude Code, skill-smith runs only when called, and UPDATE shows a diff for each file before applying it. Automatic runs (a Stop hook) can come later if manual runs prove the rules hold.

## Not depending on the authors' setups (0.1.0)

skillify-pro relies on `compound-engineering:*`, `watch-video`, `pm`, `second-brain` and a `repos.yaml`. skillify (OMC) writes flat `.md` files that Claude Code does not load as skills. skill-smith uses only `rg`, `gh` and git. For deep evals it points to Anthropic's [skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md), when that skill is available.

## Its own wiki and changelog (0.1.0)

The author asked for it: skill-smith keeps its own `.wiki/` and follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Lessons go to [lessons.md](lessons.md) first, then move into SKILL.md when they repeat. This is Hermes' self-improvement loop, applied to the skill that does the improving.

## Its own public repo, MIT (0.1.0)

skill-smith was born inside a private monorepo and moved to its own public repo, [biliboss/skill-smith](https://github.com/biliboss/skill-smith), so it can be installed with `npx skills add biliboss/skill-smith`. The skill sits at the repo root, so the repo *is* the skill folder. It is installed as a copy, not a symlink.
