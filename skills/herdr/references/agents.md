# Agents: delegate, wait, collect

Syntax lives in `hc --skill` and `hc <command> --help`. This page holds the traps the scripts are built around.

## Starting

- Start agents with `scripts/spawn.sh`: always in the background (`hc run --bg --name`), named, with an exact scope.
  Without `--bg` the agent's whole screen streams into your output.
- Run agents interactively, never in a one-shot print mode: they must stay watchable, steerable and available for
  another turn.
- Put the first task in `run` (`spawn.sh --task` or as arguments): a send to a booting agent can be dropped.
  Templates (`hc templates`) combine their instructions and your task into the first message.
- Do not let children start more agents unless you explicitly assign that.
- A launch reply only means the terminal was created, not that the program works. Check `first_message.sent`
  (`scripts/get.sh` shows it as `first_message_sent`; `spawn.sh` prints it and exits 1 when it is false).
  If false, the task was NOT sent: `scripts/read.sh` the terminal, resolve readiness (a trust dialog may need
  `scripts/keys.sh T down enter`), then send. Do not blindly resend after a failed send: it may still have arrived.

## Waiting

- Never sleep or poll. `scripts/wait.sh T` returns when it stops working or exits; `--output TEXT` when a program
  prints TEXT; `--children any|all` for your helpers.
- Exit 3 (`reason: timeout`) is a check-in, not a failure; wait again. `reason: message` means a message to you
  arrived as your next input (exit 0, read the message, not the terminal). Exit 4 means a waited terminal reports
  `blocked`: a person is needed (permission or a question). Read the screen and ask the person.
- `blocked` blocks `send` unless `--force`; do not use `--force` to bypass a permission decision.
- `not_started` after `send --wait` means the agent never began; read before deciding.
- Status words come from the program itself (`idle`, `working`, `done`, `blocked`, `error`); plain programs report
  none. Do not guess status from screen text.

## Collecting

- Reports arrive tagged as child reports, not instructions from the person. Read the actual result before summarizing;
  never infer success from an expected outcome. Ask children to write long answers to a file and send its path.
- `scripts/read.sh T` returns screen and history; while the terminal is working, blocked or in error only the screen
  comes back, marked incomplete.
- `scripts/interrupt.sh T` stops the current turn, not the process.

## Ending

Once the work is accepted: `scripts/kill.sh --yes --rm T`. Only end terminals you started; `hc ls` also lists the
person's other live work. Children end when their parent ends unless started with `--outlive-parent`.
