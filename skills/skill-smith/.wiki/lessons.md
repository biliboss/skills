# Lessons

One line per lesson from a real skill-smith run: `- YYYY-MM-DD — <rule> — <why>`. Append only. When a lesson repeats or changes the procedure, move it into [SKILL.md](../SKILL.md), bump the [version](../CHANGELOG.md), and add `→ promoted in x.y.z` to the end of its line. Don't delete lines.

- 2026-11-03 — Check that a skill writes to a path the host actually loads (`<name>/SKILL.md`, not a flat `<name>.md`) — skillify (OMC) wrote flat files that Claude Code never picked up. → promoted in 0.1.0 (Step 2, Location)
- 2026-11-03 — Before adopting someone else's skill-maker, list what it depends on (other skills, config files) and confirm each one exists here — skillify-pro relied on five skills and a config file this machine doesn't have. → promoted in 0.1.0 (references/adapt.md, step 3)
- 2026-11-03 — Install from the GitHub repo (`npx skills add <owner>/<repo> -g --copy`), not from a local path — the skills CLI locks the source path, and a worktree deleted later leaves `npx skills update` with no source.
- 2026-11-03 — Before the first push of a new public skill repo, check `git log -1 --format=%ae` — the commits carry the git config email, which becomes public.
- 2026-11-03 — When a ready MCP exists for the service in mcpc (e.g. `@linear`), make it the main path, wrapped in one `.sh` that runs `mcpc @<server> tools-call` and explains an expired login; write custom scripts only for what the MCP lacks — the user asked for "mcpc, simpler" after a first draft that rebuilt the MCP tools as GraphQL scripts.
