---
name: thread
description: Use when opening a topic/thread of a card in one call, or the owner says "thread", "tópico", "abre um tópico", "abre uma thread do card", "branch da sessão do card". Opens a tmux window in the card's session running a Hermes session (a /branch of the card's session, or a new one) named '<card> · <topic>', with the brief passed inline (argument, stdin heredoc or gzip+base64), no temp file. Also lists and closes threads. Not for kanban cards themselves (kanban) nor generic panes (tmux).
metadata:
  version: 0.1.0
---

# thread — a topic of a card, in one call

One call = tmux window `<topic>` in session `<card-slug>` + Hermes session titled `<card-slug> · <topic>` + the brief delivered. No file in temp: the brief is pasted from stdin into a tmux buffer (bracketed paste, so multi-line text is ONE message; no ARG_MAX or send-keys limit).

## Use

```bash
T=<this skill>/scripts/thread.sh
$T open unicred acesso-bubble --brief - <<'EOF'
Context, goal, what to return. Any size, any quotes.
EOF
```

- `--branch` (default when a Hermes session titled `<card-slug>` exists): `hermes --continue <card>` then `/branch <card> · <topic>`, so the thread inherits the card's context.
- `--new`: a fresh session, renamed `<card> · <topic>` once its id appears (the one created after the window opened).
- `--brief TEXT` inline; `--brief -` stdin (use a quoted heredoc `<<'EOF'` so the shell expands nothing); `--brief-gz B64` = base64 of gzip, when your tool parameter is size-limited (`gzip -c f | base64`).
- `--profile` (default `bili`), `--cwd DIR` (default `$PWD`).
- Output, one line: `window=<card>:<topic> (@id) title='…' session=<id> mode=…`.
- `thread.sh list [<card>]` lists threads (windows marked `@thread`); `thread.sh close <card> <topic>` kills only the window, the Hermes session stays.

## Rules

- Never put a secret in a brief: it lands in the session history.
- Card and topic: no quotes, `$` or backslash (refused). One window per topic; a duplicate is refused.
- The session `<card>` is created if missing; window 1 is named by the kanban title when kanban knows the card, and windows get `@card=<id>`.
- Readiness is polled on the pane (`ready`/`opus`/`sonnet`, 40 s max, `THREAD_READY_TIMEOUT`); on timeout the window stays open and the brief is not sent.
- Don't touch other sessions' windows; `TMUX_SOCKET` selects another tmux server (tests use a private one).

Tests: `scripts/test.sh`. Credits: [README.md](README.md). History: [CHANGELOG.md](CHANGELOG.md).
