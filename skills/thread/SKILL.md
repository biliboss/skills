---
name: thread
description: Use when opening a topic/thread in one call, or the owner says "thread", "tópico", "abre um tópico", "abre uma thread do card", "branch da sessão". Opens a tmux window in the session where the skill was invoked (never a per-card session) running a Hermes session, a /branch of the one that invoked the skill, titled '<card> · <topic>' (or '<topic>'), the card linked on the window (@card), the brief passed inline (argument, stdin heredoc or gzip+base64), no temp file. Also lists and closes threads. Not for kanban cards themselves (kanban) nor generic panes (tmux).
metadata:
  version: 0.9.0
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
- `thread.sh list`: every window marked `@thread`, across sessions (`session  topic  window-id  card`). `thread.sh close <topic> [--session S]` (see Closing a thread): kills that window only (the Hermes session stays); refused when the topic is open in more than one session and no `--session`.

## Rules

- **Uma thread começa em shape.** O brief colado em toda thread nova leva na frente uma linha mandando carregar a skill `shape` e registrar com `shape.sh emit request.received --shaping <topic>`. Por quê: regra do dono, o sistema TEM de experimentar; abrir uma thread já é começar um shape daquele contexto, e o domínio shape registra o shaping de cada thread. A linha some se o brief já cita shape ou com `--no-shape`.
- **Never move the owner's focus: tabs open in the background with -d** (`new-window -d -a`; never `select-window`/`switch-client`; a restart is `respawn-window` alone). A thread must not take the owner off the window he is on.
- Never put a secret in a brief: it lands in the session history.
- Card, topic and session: no quotes, `$` or backslash (refused). One window per topic per session; a duplicate is refused.
- The cost clock follows the active window's `@card` first, then the session name (cost-track); that is why the card is set on the window.
- Readiness is polled on the pane (`ready`/`opus`/`sonnet`, 40 s max, `THREAD_READY_TIMEOUT`); on timeout the window stays open and the brief is not sent.
- Don't touch other windows; `TMUX_SOCKET` selects another tmux server (tests use a private one).

Tests: `scripts/test.sh`. Credits: [README.md](README.md). History: [CHANGELOG.md](CHANGELOG.md).

## Closing a thread

- **A task thread closes itself when its work is DONE**: the "como conferir" passed and what had to land landed (PR merged, `wt remove`, main clone pulled). The agent's last step: `thread.sh close --self --summary "<o que mudou>"` (target: the window whose `@hsid` is `$HERMES_SESSION_ID`, else `$TMUX_PANE`'s window).
- **A conversation/question thread closes when the owner (or the Bili) says so**: `thread.sh close <topic> [--by owner|bili] [--summary TEXT]`.
- **Never close while it waits for the owner**: an open question, an approval, one of his 4 cases (money, login, publishing, deleting). It stays lit (✓/◆).
- **Never close while it has subagents running**: the tab shows one grey glyph + the count (`@subagents`, kept by `agent-state.sh sub+`/`sub-` from the Hermes `subagent_start`/`subagent_stop` hooks, matched by `parent_session_id`); `close --self` refuses while it is above 0 and the ✓ only lights when it drops to 0 after the turn ended.
- **Closing kills only the tmux window.** The Hermes session stays, resumable.
- **Never move the owner's focus**: if he is ON that tab, the close is deferred (`@closing`); it happens when he leaves (`session-window-changed` hook, or the next `thread.sh touch`/`sweep`).
- **Every close writes one line** to `~/.local/state/threads.log` (`THREAD_LOG`): `when<TAB>topic<TAB>card<TAB>session id<TAB>summary<TAB>self|owner|bili`.
- **The brief ends with**: `Ao terminar: se for tarefa e estiver entregue (merge feito), rode thread.sh close --self --summary "<o que mudou>"; se esperar o Gabriel, não feche.`

## Tabs: MRU with an attention band

The order is an **MRU list** (most recently used first: the term of the cache literature, and the order of macOS's ⌘Tab), with an **attention band** in front. `thread.sh sort [<tab>] [--now]` applies it to the tab's session in one go: it computes the wanted order and moves only what is out of place.

1. **Tab 1 is the Bili** (the session's first window). **Windows without `@thread`** (zsh…) stay **last**, in their own order.
2. Between them, three bands: **needs the owner** (`@ask` ◆ open question, `@done` ✓ finished and not seen), then **working** (`@agent=working` or `@subagents` > 0), then **idle and seen**.
3. Inside a band, **the highest `@touched` first** (ms; ties keep the current order). `sort <tab>` stamps `@touched` on that tab when it is a thread.
4. **The owner's tab never moves**: it keeps its index and the focus (`move-window -d` around it).
5. **Debounce** of ~2 s (`THREAD_SORT_DEBOUNCE`, `0` = inline): a burst of events is one sort, so tabs do not jump on every hook. `--now` skips it.
6. **Numbers stay 1..N** (`move-window -r` at the end; `renumber-windows on` covers closes).

The state lives in window options (`@ask`, `@done`, `@agent`, `@subagents`, `@touched`; the session's `@sortreq` is the debounce token), no extra file. The tmux skill's `agent-state.sh` calls `thread.sh sort <pane>` from the Hermes hooks: `pre_llm_call`, `post_llm_call`, `subagent_start/stop`, and `on_human_input_request/resolved` (◆ `ask`/`answered`). `thread.sh touch <tab>` is the old name: `sort <tab> --now`. Tests: `scripts/test-sort.sh` (private tmux server).

## Thread view: the thread as a screen, not a chat

`scripts/threadview.py <hermes-session-id>` is a fullscreen TUI (Rich, no Textual) for one thread, opened in a tmux
tab: the agent builds the screen, the owner types at the bottom. Prototype; one turn = one `hermes --resume <id> -z`.

- **The agent's only output is the screen** (`scripts/view.py <sid> …`: goal, steps, artifacts, decision, pulse,
  workers); its chat text is discarded. State lives in `~/.local/state/threadview/<sid>.json` (`THREADVIEW_DIR`).
- **The input is a queue**: each message is one line above the input (`⋯` waiting, `✓` received, `✓✓` read, a timer
  while it works, `✓ ↻ <what changed>` when answered) and leaves once answered. One turn at a time, in order.
- **A turn has 10 s.** Longer work goes to a worker (`view.py worker add/done`), shown in the Agentes queue at the top.
  A turn past 10 s only counts as answered with a line in `<sid>.overrun.log`.
- **A choice turns the input into the choice**: options with the agent's confidence summing 100, best first, moved
  with j/k and sent with ⏎; a tournament (skill `choice`, a dependency of this skill) turns it into fixed keys per edge.
  `o` opens the showcase, in the dev-console when `devc` is installed.
- **ctrl+l** shows the component names (Goal, Steps, Artifacts, Decision, Pulse, Queue, Input).
- Headless `--resume` on a long session makes Hermes compact it (old rows `active=0`); the live tab still holds the old
  history in memory, so don't type in both at once.

## Estado em tempo real

`thread.sh state [<aba>]` dá uma linha JSON por thread: sessão, índice, tópico, estado (`working` ●, `ask` ◆, `done` ✓, `idle`), subagentes, `touched` (ms) e cartão.

`thread.sh watch` imprime o estado atual e depois uma linha a cada mudança, ao vivo, do NATS local (`mesa.thread.state.changed`, `THREAD_NATS_URL`). O dev-console e a barra nativa assinam o mesmo assunto.

Evento na escrita, não consulta periódica: quem grava o estado (o `agent-state.sh` da skill tmux, e o `sort` ao reordenar) publica na hora, por `scripts/thread-state.sh`, que fala o protocolo do NATS direto no `/dev/tcp` do bash, sem abrir processo. Por que não o control mode do tmux (`refresh-client -B`, `%subscription-changed`): o man do tmux 3.7 diz que ele avisa "at most once a second", lento para a meta de 50 ms.

Medido (`scripts/test-state.sh`, tmux privado): da gravação à linha no watch, mediana de 33 a 53 ms com a máquina em carga 30 em 10 núcleos. Sem NATS no ar, o `state` funciona e o `watch` diz que não há fonte ao vivo.

