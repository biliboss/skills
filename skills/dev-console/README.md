# dev-console

A read-only, full-screen web console for an event-sourced project in development: the state machine of its commands
and events drawn from the code, the entities, the journal and widgets per event. Agents read `SKILL.md`; this is for people.

## Run it

```sh
uv run --script scripts/dev-console.py --project scripts/dev_console_project.py --port 5057
```

It listens on 127.0.0.1 only. One `--project` per domain. ⌘K switches the domain, ⌘P the module.

## Modules

- **Domain**: the project's tabs (model, entities, events, journal).
- **Playground**: the design-playground canvas inside the console.
- **Agents** (`/agents`): the prompts you typed to Claude Code and the agents' session logs, live. It reads
  `~/.claude/projects` (change with `DEV_CONSOLE_AGENTS_DIRS`), only in memory, never writes or logs the text.
  Tests: `uv run --script scripts/test_console_agents.py`.

## History

`CHANGELOG.md`. How the screen works and why: `SKILL.md` and `references/console-ui.md`.
