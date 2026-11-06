# skill-smith

Creates, updates and adapts agent skills (`SKILL.md`), so the next session does a class of task right on the first try.

The agent's instructions are in [SKILL.md](SKILL.md). This page is for people reading the repository.

## What it does

Three modes, picked by what you ask for:

| Mode | When | Result |
|---|---|---|
| CREATE | a workflow worked out in a session, or "make this a skill" | a new skill folder with `SKILL.md`, `README.md` and `CHANGELOG.md` |
| UPDATE | a correction or lesson about a class of task | the lesson folded into every skill it touches, with a diff per file |
| ADAPT | a skill from outside (a URL, a path, pasted text) | a port with a license check and attribution, see [references/adapt.md](references/adapt.md) |

It prefers patching an existing skill over making a new one, and it refuses to capture environment failures, negative claims about tools and one-off tasks.

## What a skill folder holds

- `SKILL.md`: the agent's instructions, and the only place a rule is written.
- `README.md`: the human page (this kind of page): what it is, how it works, the commands, how to test, a link to the history.
- `CHANGELOG.md`: the history, in Keep a Changelog format.
- `scripts/` and `references/` when needed. Actions are `.sh` scripts, not an MCP server.

## Where things are

- [CHANGELOG.md](CHANGELOG.md): the history of skill-smith.
- [ATTRIBUTION.md](ATTRIBUTION.md): the sources it borrows from.
- [.wiki/](.wiki/README.md): its own small memory about running itself.
