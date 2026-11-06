---
name: handoff
description: >-
  Use when a Hermes agent's session in tmux has grown long and must start clean without losing anything, or the owner
  says "handoff", "passagem de turno", "limpa a sessão", "começa do zero mas guarda", "salva as últimas sessões do
  bili". Logs the session (id, title, context, last message) to a JSONL, branches it offline into a tab right of the
  agent's, and only when the copy is up sends /new plus a short summary to the original. `handoff.sh log` lists the
  last sessions with the resume command. Not for opening a topic (thread) nor compacting in place (/compress).
metadata:
  version: 0.1.0
  license: MIT
---

# handoff: the shift handover of an agent session

**The name.** *Handoff* is the shift handover of nursing and aviation (SBAR, the I-PASS studies; the ATC position
relief briefing): who leaves hands the state to who comes in, out loud, before leaving. Here the long session is who
leaves, the clean session is who comes in, and the branch keeps everything that was said.

## What the owner means by "handoff"

**"Faz o handoff desta sessão" means step 1 only: the log line** (session id, title, context, last message), so the
session can be found and resumed later. The branch tab and the `/new` are a separate, explicit ask ("limpa a sessão",
"começa do zero", "abre o branch"). When the words do not say clean or branch, write only the log line (same fields,
same file) and say the resume command; never launch the full script "to be safe": with `--detach` it runs the moment
the turn ends, nothing in the same turn can stop it, and it clears the owner's live tab (the desktop chat and the
Bili's tmux tab are the same session).

## Use

```
handoff.sh [<tmux target>] [--from <session id>] [--detach]   # target default: $TMUX_PANE (the caller)
handoff.sh log [N]                                            # the last N handovers, with `hermes -p bili --resume <id>`
```

Order, and nothing is skipped:

1. **Log first.** One line in `~/.local/state/bili-sessions.jsonl`: `{at, session_id, title, context, last_message,
   tmux}`. The context is read from the Hermes status bar (`244.6k/1M`); the last message from
   `hermes sessions export --only user-prompts`. Whatever fails later, the session can be found and resumed.
2. **The lock.** The agent must be idle (its bar says `ready`). Mid-turn, the script waits for the turn to end, at most
   `HANDOFF_IDLE_TIMEOUT` (600 s); past it, nothing else happens (only the log line).
3. **Branch.** An offline fork of the session (the `thread` skill's `fork.py`: a child row, the source untouched)
   opens in a tab **right of the agent's**, in the same tmux session, in the background (`new-window -a -d`: the
   owner's focus is never moved), named `<tab> antes` through the `thread()` Value Object (`bili antes`).
4. **Clean.** Only when the copy shows `ready`: `/new` in the original tab, then one pasted summary (where the old
   conversation went, the tab, the log, the resume command, the plan to read). A fork failure, a copy that never gets
   ready, or the agent busy again: the original is left as it was.

The session id comes from `--from`, else the window's `@hsid` (threads have it), else `$HERMES_SESSION_ID` when the
target is the caller's own pane. None of them: refused, nothing changed. When the caller hands **itself** over, steps
2 to 4 run detached (its turn only ends after the script returns); their output goes to
`~/.local/state/bili-sessions.handoff.log`.

## Pitfalls

- Targets are ids (`%N`, `@N`): a session name with a dot (`sygnal 0.2`) in `=name:` is read by tmux as a pane
  separator and once killed the wrong tab.
- Never run the full script on the Bili's real session unless the owner asked to clear it: it does clear the tab.
  The desktop chat's `$HERMES_SESSION_ID` is the session running in the Bili's tmux tab (find it by
  `pane_start_command` empty + the context number on its bar), so "this session" from the desktop is that tab.
- The Bili's own tab has no `@hsid` (only threads do): handing it over from outside needs `--from <id>`; take the id
  from `hermes -p bili sessions list` (the row whose title/last activity matches) and say which one before running.
- Idle means `ready` in the **last 3 non-blank lines** of the pane, not anywhere on screen: the model name (`opus`,
  `sonnet`) is on the bar even mid-turn, so the thread skill's looser readiness check would let a busy agent through.
- Optional JSONL fields go as `if $x=="" then null else $x end`, never `($x|select(.!=""))` inside the object:
  `select` yielding nothing drops the WHOLE object, and the log line silently never gets written.
- The thread skill's fake hermes keeps control keys as text (`C-u` lands as `\x15` before `/new`): match the end of
  the message (`/new$`) in tests, not the whole line.
- The summary tells the clean session to read the plan; the branch keeps the history, so ask it, not the log.

## Tests

`scripts/test.sh`: the `thread` skill's fake hermes on a private tmux server (`-L handoff-test-<pid>`), a session
name with a dot; covers the refusal without an id, the log line, the fork, the tab position, the focus, `/new` then
the summary, `log`, a busy agent (timeout: no fork) and a failed fork (nothing sent).
