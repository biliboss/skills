---
name: thread
description: Use when opening a topic/thread in one call, or the owner says "thread", "tópico", "abre um tópico", "abre uma thread do card", "branch da sessão". Opens a tmux window in the session where the skill was invoked (never a per-card session) running a Hermes session, a /branch of the one that invoked the skill, titled '<card> · <topic>' (or '<topic>'), the card linked on the window (@card), the brief passed inline (argument, stdin heredoc or gzip+base64), no temp file. Also lists and closes threads. Not for kanban cards themselves (kanban) nor generic panes (tmux).
metadata:
  version: 0.3.0
---

# thread — a topic, in one call

One call = a tmux window `<topic>` **in the session where you are**, right after the invoking agent's window (so the newest thread is always tab 2) + a Hermes session titled `<card> · <topic>` (just `<topic>` without a card) + the brief delivered. The card is a link on the window (`@card=<id>`, which the cost clock reads), never a session of its own. No file in temp: the brief is pasted from stdin into a tmux buffer (bracketed paste, so multi-line text is ONE message; no ARG_MAX or send-keys limit).

## Use

```bash
T=<this skill>/scripts/thread.sh
$T open <topic> [--card C] [--session S] [--from SESSION_ID | --new] [--brief TEXT | --brief - | --brief-gz B64]
$T open acesso-bubble --card unicred --brief - <<'EOF'
Context, goal, what to return. Any size, any quotes.
EOF
```

- **Where the tab opens**: the caller's session (`$TMUX_PANE`'s, i.e. `tmux display-message -p '#S'`). Not inside tmux (the Hermes desktop agent): the session of the owner's most recently active client (`tmux list-clients -F '#{client_activity} #{client_session}' | sort -rn | head -1`). `--session S` overrides. No client and no `--session`: refused. Never a session per card.
- `--card C`: slug or id, resolved by kanban; the window gets `@card=<id>`, the Hermes title is `<C> · <topic>`. Without it the title is `<topic>` and the window has no `@card`.
- **A thread is ALWAYS a branch of the Hermes session that invoked the skill**: `$HERMES_SESSION_ID` (set in every Hermes agent's environment). The branch is made OFFLINE by `scripts/fork.py` (Hermes's own `SessionDB`, run with Hermes's interpreter: same lineage as `/branch`, i.e. `parent_session_id` + `_branched_from`, system prompt and transcript copied, titled) and the window runs `hermes -p <profile> --resume <NEW id>`, waits for `ready`, then pastes the brief. The source is never resumed, attached to or ended, so a LIVE chat (the desktop one) gets no second client and no stray message. `--from SESSION_ID` branches from another session. `--new` (fresh session, renamed once its id appears) only when explicitly asked. `HERMES_SESSION_ID` empty and no `--from`: refused with a message, nothing opened. `fork.py <source-id> <title> [--profile P]` prints the new id (usable alone; `--profile` wins over an inherited `HERMES_HOME`).
- **Placement**: `tmux new-window -a` right after the invoking agent's window (the window of `$TMUX_PANE` when it is in the target session; for the desktop caller, the session's first window), pushing the others right.
- `--brief TEXT` inline; `--brief -` stdin (quoted heredoc `<<'EOF'` so the shell expands nothing); `--brief-gz B64` = base64 of gzip, when your tool parameter is size-limited (`gzip -c f | base64`).
- `--profile` (default `bili`), `--cwd DIR` (default `$PWD`).
- Output, one line: `window=<session>:<topic> (@id) title='…' card=<id|-> session=<id> mode=…`.
- `thread.sh list`: every window marked `@thread`, across sessions (`session  topic  window-id  card`). `thread.sh close <topic> [--session S]`: kills that window only (the Hermes session stays); refused when the topic is open in more than one session and no `--session`.

## Rules

- Never put a secret in a brief: it lands in the session history.
- Card, topic and session: no quotes, `$` or backslash (refused). One window per topic per session; a duplicate is refused.
- The cost clock follows the active window's `@card` first, then the session name (cost-track); that is why the card is set on the window.
- Readiness is polled on the pane (`ready`/`opus`/`sonnet`, 40 s max, `THREAD_READY_TIMEOUT`); on timeout the window stays open and the brief is not sent.
- Don't touch other windows; `TMUX_SOCKET` selects another tmux server (tests use a private one).

Tests: `scripts/test.sh`. Credits: [README.md](README.md). History: [CHANGELOG.md](CHANGELOG.md).
