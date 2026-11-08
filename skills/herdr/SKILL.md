---
name: herdr
description: >-
  Use when a task involves Herdr Desktop: finding where this terminal sits in the window, showing the person a new
  space, tab or split, delegating work to an agent and following it, running a long process in a terminal that
  stays alive, working on another machine, or cleaning up what you opened. Thin scripts over herdr-app (the window)
  and hc (its core, where terminals run); every state change is logged through the logging skill. Triggers "open a
  tab", "split the pane", "start an agent", "wait for the agent", "read its screen", "run this in a terminal", "run it
  on the vps", "close what I opened", "where am I in herdr". Needs bash, herdr-app, hc, jq and logging.
metadata:
  version: 0.1.0
---
# herdr

Herdr Desktop has two parts. `herdr-app` is the window: it shows spaces, tabs and panes, and only changes what the
person sees. `hc` is its core: it runs the terminals and keeps them alive when the window closes. The scripts in
`scripts/` wrap both. The syntax stays in `hc --skill`, `herdr-app --skill` and `herdr-app commands`; read those
for anything the scripts do not cover, and use `scripts/do.sh` for the rest of the catalog.

Every script has `-h`. Data goes to stdout (TSV; `--json` for the raw reply), errors to stderr. Exit codes: 0 ok,
1 not found or failed, 2 usage, 3 timed out, 4 blocked on a permission, 5 done but the end log failed. Every
script that changes state takes `-n` (print the exact command, run and log nothing).

## 1. Where am I

Start here: `$HC_TERMINAL_ID` is a terminal address (`t7`), never a pane id, and the window addresses things by
pane, tab and space.

- `scripts/whereami.sh` maps this terminal to its pane, tab and space.
- `scripts/ls.sh` lists spaces, tabs and terminals in the window; `--core` lists every live hc terminal instead.
- `scripts/status.sh` shows layout, focus, zoom, overlays and file or mod errors; exit 1 when it reports errors.

## 2. Show something to the person

New spaces and tabs appear immediately: create them only when asked, and always with a name. Use ids from `ls.sh`.

- `scripts/space-new.sh --name N` and `scripts/tab-new.sh --name N` (optionally `--folder`, `--argv`, `--task`).
- `scripts/split.sh --place right|down` opens a terminal beside this pane; it refocuses this pane first when the
  focus is elsewhere, because the split lands beside the focused pane; `--pane ID` splits another pane instead.
- `scripts/focus.sh pane|terminal|agent|tab|space ID`, `scripts/rename.sh space|tab ID NAME`,
  `scripts/zoom.sh [PANE]`, `scripts/settle.sh [--undo] [TAB]`, `scripts/layout.sh [NAME|--next]`.
- `scripts/shot.sh [FILE.png]` saves the window's last frame and prints the path. Look at the picture before saying
  it looks right.

## 3. Delegate to an agent and follow it

Details and traps in `references/agents.md`.

- `scripts/spawn.sh --name N --cwd DIR --task TEXT -- PROGRAM` starts it in the background with its first task in
  the launch. A send to a booting agent can be dropped, so the task goes here, not in a later `send`.
- `scripts/get.sh T` shows state, status and `first_message_sent`. `false` means the task was not delivered: read it,
  never resend blind.
- `scripts/wait.sh [T]` waits for it to stop working, `--output TEXT` for text it prints, `--children any|all` for
  helpers. Exit 3 is a check-in (wait again), 4 means it is blocked on a permission: read it and ask the person.
- `scripts/read.sh [--lines N] T` prints its screen and history.
- `scripts/send.sh T TEXT|-` pastes text and presses Enter; `scripts/keys.sh T enter down ...` presses keys;
  `scripts/interrupt.sh T` stops its turn, not its process; `scripts/label.sh T k=v` sets labels.

## 4. Run a process

- `scripts/run.sh --name N [--cwd DIR] [--wait | --ready TEXT] -- CMD...` runs a slow or long-lived command (build,
  tests, server) in a named background terminal, so your own shell stays free. `--wait` returns its result when it
  exits; `--ready TEXT` returns when it prints TEXT. Read the output afterwards with `read.sh`.

## 5. Another machine

Details in `references/remote.md`.

- `scripts/machines.sh` lists the machines hc can reach. Adding one is the person's setup; do not do it unasked.
- `scripts/remote-exec.sh --on M -- PROGRAM ARGS` runs one program there and returns exactly what it wrote.
- `scripts/remote-file.sh read|write|edit --on M PATH` reads, replaces or edits a file there. Use it, not your local
  file tools, for remote paths. `spawn.sh --on M` and `run.sh --on M` start terminals there.

## 6. Clean up what I opened

Close only what you opened; the window holds the person's other work. Never stop or restart the app or the core.
Details in `references/safety.md`.

- `scripts/close.sh --yes space|tab|pane ID` closes it and ends its terminals. It refuses without `--yes`, for ids
  not shown, and for anything containing this terminal.
- `scripts/kill.sh --yes [--rm] T` ends a terminal's program (and removes it with `--rm`). It refuses without
  `--yes` and to kill itself.

## 7. Something went wrong

- `scripts/doctor-status.sh` checks versions, that the window and core answer, window errors, and terminals that are
  blocked or in error. Read-only.
- A launch reply only means the terminal was created, not that the program works: `read.sh` it.
- `scripts/feedback.sh TEXT|-` drafts a report for the person to review and send. Nothing is sent by itself.

## 8. Customize

Layouts, keys and mods are the person's configuration: make only the change asked for. The procedure, the check
and the screenshot loop are in `references/mods.md`; surfaces and their commands in `references/surfaces.md`.

- `scripts/do.sh --list [PATTERN]` lists the catalog; `scripts/do.sh COMMAND --key value` runs a command that has
  no dedicated script.

## Requirements

`bash` (macOS 3.2 compatible), `herdr-app`, `hc`, `jq`, and the `logging` skill. `scripts/check.sh` verifies them
without touching the window.

Logging: set `LOGGING_EMIT` to the logging skill's `scripts/emit.sh`, in the environment or as a `LOGGING_EMIT=`
line in `${BILIBOSS_ENV:-$HOME/.config/biliboss/.env}` (the file is read as text, never sourced; see the repo's
`example.env`). Each state-changing script emits `herdr <script>.start` before and `<script>.end` after, with one
shared trace id. If the start record cannot be written, the script exits 1 and does nothing. Text sent to agents,
task arguments and file contents are never logged, only their lengths (`text_len`).
