# Attribution

skill-smith is original writing that combines ideas, and some adapted rules, from three MIT-licensed projects. All three allow reuse as long as their copyright notice is kept, so it is kept below.

| Source | What skill-smith took | Pinned revision | License |
|---|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent), Nous Research | The content rules ([`_LESSON_LAYER_BLOCK`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L390-L420)), the do-not-capture list ([`_DO_NOT_CAPTURE_BLOCK`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L422-L446)), the patch-before-create order ([`_SKILL_REVIEW_PROMPT`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L448-L520)) and read-before-write ([`skill_manager_guards.py`](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/skill_manager_guards.py)) | [`bf0203a`](https://github.com/NousResearch/hermes-agent/tree/bf0203a794a07aac3ff764972ab9087baa4e4f4e) | [MIT](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/LICENSE) |
| [skillify](https://github.com/Yeachan-Heo/oh-my-claudecode/blob/0564555b63dfedd158669c6799d53743abd7d6bf/skills/skillify/SKILL.md) in oh-my-claudecode, Yeachan Heo | The three-question worth-it gate | [`0564555`](https://github.com/Yeachan-Heo/oh-my-claudecode/tree/0564555b63dfedd158669c6799d53743abd7d6bf) | [MIT](https://github.com/Yeachan-Heo/oh-my-claudecode/blob/0564555b63dfedd158669c6799d53743abd7d6bf/LICENSE) |
| [skillify (skillify-pro)](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/skills/skillify/SKILL.md) in makerskills, Corey Haines | UPDATE mode (cross-skill propagation, per-file diffs, [semver rules](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/skills/skillify/references/update-versioning.md)), ADAPT mode ([three buckets](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/skills/skillify/references/adapt-buckets.md), [license gate](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/skills/skillify/references/adapt-license-check.md)) | [`ea7dd78`](https://github.com/coreyhaines31/makerskills/tree/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c) | [MIT](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/LICENSE) |

Also referenced, but not copied: Anthropic's [skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) for evals, the [Agent Skills spec](https://agentskills.io/specification), [Claude Code skills docs](https://docs.claude.com/en/docs/claude-code/skills), [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

To check for upstream changes: `gh api repos/<owner>/<repo>/commits/HEAD --jq .sha` and compare with the pinned revision.

## Upstream notices

> Copyright (c) 2025 Nous Research — MIT License
>
> Copyright (c) 2025 Yeachan Heo — MIT License
>
> Copyright (c) 2026 Corey Haines — MIT License

Each of these is distributed under the MIT License, whose full text is in [LICENSE](LICENSE). The only difference in each case is the copyright line above.
