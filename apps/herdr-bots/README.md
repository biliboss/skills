# Herdr Bots

`AGENTS.md` has the screen and widget map.

Requires macOS or Linux, Python 3, `hc`, `herdr-app`, a running Herdr window, and the configured agent command.
Old-folder preparation additionally requires `lsof`. Herdr must expose `layout.clone`, `mod.clone`, terminal
labels and the installed gpui-kit mod API. No Node packages or new repository are needed.

Create `~/agents/bots.json` locally, or use `--bot` below. Example (replace the UUID with your own):

```json
{
  "bots": [{
    "id": "assistant",
    "name": "Assistant",
    "folder": "~/agents/assistant",
    "command": ["claude"],
    "session_id": "00000000-0000-4000-8000-000000000001"
  }]
}
```

Commands are argv arrays, never shell strings. The command must support Claude's `--session-id` and `--resume`
arguments. IDs and session UUIDs must be unique. `AG_HOME` changes the data directory; `AG_BOTS_FILE` overrides
the registry path. The installer records both in the mod props, so UI and scripts read the same registry.
Authentication and normal Claude user configuration remain available. Automatic Claude memory is disabled for bot launches so a reused folder path cannot reload old auto-memory. No old instance content is copied.

From this directory:

```sh
./install.sh --bot assistant Assistant ~/agents/assistant 00000000-0000-4000-8000-000000000001
# Existing registry and instances: ./install.sh
scripts/ag-open assistant
```

The installer checks all local process working directories and live core terminals before moving an existing
instance to `<folder>.backup-<timestamp>`. The rename preserves the entire tree, including hidden files,
permissions and symlinks. It then creates only an empty `AGENTS.md`, `CLAUDE.md` containing `@AGENTS.md`, and
`.claude/settings.json` containing `{}`. If inspection fails or a process uses that folder, preparation stops;
no session is killed. A local preparation marker makes reinstalls preserve the new instance as well.

The active layout is cloned to `bili-bots`. A clone of the Spaces mod filters the workspace IDs published by
Bots from the validated registry; it has no second registry. The shipped mods and layouts remain untouched.
Reinstallation reuses the private layout, mod clones and section. The layout must have the standard `sidebar`,
`brand` and `spaces` nodes, and a Spaces mod importing the Herdr spaces API. Unsupported layouts fail clearly.
Mod paths refer to this checkout: keep it installed, or rerun the installer from its new location.

Each bot has a stable core terminal name derived from its ID and UUID, plus `bili.bot` and `bili.session` labels.
Rule: creating or opening never moves the owner's focus; only the panel click and Option+1-9 pass `--focus`, and tests that change focus never run on the owner's Herdr. A live match is focused on click (in the background otherwise); a parked match is adopted into its own workspace. Otherwise the core starts the
launcher with explicit workspace labels. Locks and unique core names prevent duplicate starts, including
concurrent clicks. Ambiguous multiple matches fail rather than choosing by folder.

The first attempt uses `--session-id UUID`. Subsequent attempts, and any existing transcript, use `--resume UUID`.
The marker is written before launch: even a failed initial attempt requires explicit diagnosis; it does not
reset to creation. A blank Claude session may have no persistent transcript until the first message, so
closing it before writing can make resume fail. No prompt is seeded automatically. Failed resumes never
fall back. Inspect the terminal's output and `hc get <address>` for command errors. The launcher persists failed exits locally and Bots shows the diagnostic on its next registry refresh. The current user's global hooks and settings may report their own startup errors.

Verification:

```sh
python3 scripts/test_bots.py
herdr-app check .
herdr-app status
herdr-app shot /tmp/herdr-bots.png
```

A real restart should be verified when the user next closes and opens Herdr. Layout structure is saved in the
private JSON; selection and sidebar width are saved by Herdr. Do not stop the user's app or other terminals.

## Command navigation

In the personal Bots layout, Cmd+1…9 selects bots first, then visible workspaces, and Option+1…9 takes over tab selection (Cmd+digit's default). Outside this layout nothing changes. On macOS, shortcut labels appear only while Command is held. Installation builds a small helper with Xcode command-line tools: it reads only the current Command modifier flag, captures no keystrokes, and exits on a change or after 18 seconds. Herdr owns each bounded call; no detached watcher is installed.

## Layout

In the personal Bots layout the Bots panel fills the sidebar between the brand block and the footer; the Spaces and Agents lists are collapsed to zero height (kept, so Spaces still supplies the Cmd+digit hints for non-bot workspaces).
