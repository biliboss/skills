# Routing: task kind to owning profile

Same table as `ROUTES` in `scripts/hermes.py` (change both). The owner of the subject keeps its memory; choose by the
profile's SOUL.md, not by its model.

| Task kind | Profile | Notes |
|---|---|---|
| research (compare, read docs/web, remember what was researched) | `researcher` | |
| ui (screens, widgets, layout, CSS, Swift views) | `designer` | its SOUL.md must be its own, not a copy of bili's |
| infra (architecture, hosting, costs) | `sre` | proposes only; applying needs the owner's go-ahead |
| search, ads, seo | `via-ads` | read only (Search Console today); changes are the owner's |
| disk, Mac upkeep | `mantainer` | write its scope in SOUL.md before depending on it |
| coordination across profiles | `bili` | local orchestrator, not the VPS Bili |
| code: a feature, a fix, a PR | hacker | the builder: its own worktree, tests, diff-review, the PR |

## Facts behind the skill

- `hermes -p <profile> -z "<prompt>"` prints only the final answer; exit 0 ok, 1 no text, 2 failed or partial, 130
  interrupted; `--usage-file <json>` records session id, tokens and cost. `-z` is plain text.
- Profiles are isolated (config, `.env`, SOUL, sessions, memory, skills, cron). The docs warn never to point two agent
  processes at one profile: both write memory.
- A profile's gateway need not be up for `-z` (inferred from the docs, not tested). Each running turn on a Claude
  provider is a `claude -p` child of roughly 230-415 MB, so parallel profiles cost that each while they run.
- `hermes peer dm` targets a remote or multiplexed gateway; a local profile has no `peer`.
- Kanban (`hermes kanban create --assignee <profile>` plus `dispatch`) is the asynchronous path for long work; not wrapped yet.
- Mods: Claude Code 2.1.287+ plugin mods (`hooks/hooks.json` with `modules`) expose `$.process.spawn`; `agent.spawn`
  can rewrite a spawned agent, and replacing it with Hermes is not confirmed in the docs.
