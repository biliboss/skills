# Local agents

Bili-agents separates portable tools from machine state. It creates instances, opens configured local sessions, reads their state and collects completion evidence. The desktop transport is `hc` with `herdr-app`; native harness workers can also return evidence to a coordinator.

| Command | Example |
| --- | --- |
| Review setup | `scripts/setup -n --here` |
| Install shortcuts | `scripts/setup --here` |
| Create an instance | `scripts/ag-new sample --role hacker --project /path/to/project` |
| Create an isolated worktree | `scripts/ag-new sample --role qa --project /path/to/project --worktree /path/to/repo` |
| Preview session startup | `scripts/ag-spawn -n sample` |
| Legacy diagnostic | `scripts/ag-doctor --fast --json` |
| Strict contract | `scripts/ag-doctor --contract --all --json` |
| Isolated integration check | `bash scripts/test-integration.sh` |
| Fresh voice sessions | `AG_CLAUDE_CONFIG_DIR=/path/to/subscription-config scripts/ag-voice-probe` |

Set `AG_HOME` to a machine-specific directory outside the repository. Roles live in sibling `roles-*` skills; an instance keeps its role name in `.role`. SessionStart injects the role, and the plugin output style provides the shared voice. A new role needs its own card; unknown roles fail before opening a terminal.

The integration check verifies role injection, dry-run behavior, instance preservation, setup idempotency and worktree isolation using temporary fixtures. The voice probe starts two independent Claude print sessions in a temporary directory, with the plugin and SessionStart hook enabled. It captures response bounds and runtime logs under the user state directory. It removes API-key/provider overrides and requires an existing subscription config; it has no paid API fallback. Runtime logs must still establish that the intended style and role loaded; response length alone does not prove that.

Set `AG_MARKETPLACE` when the stable marketplace checkout is not named `biliboss`; setup also honors `CLAUDE_CONFIG_DIR`. Without a stable checkout, setup refuses versioned plugin cache links. `--here` explicitly selects version-pinned development shortcuts.

Voice controls: `AG_PLUGIN_DIR` selects the installed plugin root, `AG_VOICE_TIMEOUT` bounds each session, `AG_VOICE_STATE` selects local evidence storage, and `AG_VOICE_ROLE` defaults to `qa`. `bash scripts/test-voice-probe.sh` verifies invocation and failure handling with a fake CLI and makes no model calls.

`ag-doctor` retains the previous flags and JSON array. `--contract` uses the new YAML runner and its stricter verdict, including red evidence; its JSON document intentionally differs. House-only cleanup checks and the obsolete server backend check remain outside the public migration.

See [instructions](SKILL.md), [runtime details](references/herdr.md), [ping behavior](references/hook-ping.md) and [changes](CHANGELOG.md).
