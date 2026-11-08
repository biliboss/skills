# hermes

Claude Code and pi drive the owner's local Hermes profiles (researcher, hipster, sre, via-ads, mantainer, bili) as
agents that keep their own memory. One script, `scripts/hermes.sh`, wraps the `hermes` CLI. Rules and routing are in
[SKILL.md](SKILL.md); the routing table in [references/routing.md](references/routing.md).

How it works: `route` names the profile that owns a kind of task, `spawn` runs `hermes -p <profile> -z` from a
directory under a per-profile lock, and prints the answer plus a final JSON line with the session id, exit code,
duration and usage. task-backbrief's execute step uses it for tasks that have an owner.

| Command | Example |
|---|---|
| `list [--json]` | `scripts/hermes.sh list` |
| `route <kind>` | `scripts/hermes.sh route ui` |
| `spawn <profile> "<task>" [--cwd DIR] [--timeout S]` | `scripts/hermes.sh spawn researcher "compare X and Y" --cwd ~/src/app` |
| `resume <profile> <session> "<msg>"` | `scripts/hermes.sh resume researcher <id> "go deeper on Y"` |
| `sessions <profile> [--limit N]` | `scripts/hermes.sh sessions sre --limit 5` |
| `read <profile> <session>` | `scripts/hermes.sh read sre <id>` |
| `memory <profile>` | `scripts/hermes.sh memory researcher` |
| `dm <target> "<msg>" --owner-asked` | only when the owner asked |

Tests (a fake `hermes`, no model call): `python3 scripts/test_hermes.py`. History: [CHANGELOG.md](CHANGELOG.md).
