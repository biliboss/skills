---
name: thread
description: Use only when the owner asks for a thread. Opens a branch.
metadata:
  version: 0.10.1
---

# thread — a topic, in one call

Triggers: "thread", "tópico", "abre um tópico", "abre uma thread do card", "branch da sessão". Not kanban cards (kanban) nor generic panes (tmux).

One call = **a tmux session of its own named `<topic>`, the thread as its 1st tab** (opened detached, `@parent` = the caller's session) + a Hermes session titled `<card> · <topic>` (just `<topic>` without a card) + the brief delivered. The card is a link on the window (`@card=<id>`, which the cost clock reads), never a session of its own. No file in temp: the brief is pasted from stdin into a tmux buffer (bracketed paste, so multi-line text is ONE message; no ARG_MAX or send-keys limit).

## Use

```bash
T=<this skill>/scripts/thread.sh
$T open <topic> [--card C] [--session S] [--from SESSION_ID | --new] [--brief TEXT | --brief - | --brief-gz B64]
$T open acesso-bubble --card unicred --brief - <<'EOF'
Context, goal, what to return. Any size, any quotes.
EOF
```

- **Every thread is its own tmux session** (the owner's rule, it replaced "a tab beside the Bili"): `new-session -d -s <topic> -n <topic>`; a session already named like the topic is refused. `THREAD_TAB=1` keeps the old tab mode. Moving already-open thread tabs (or a card's tab) into sessions: per window, `S=$(new-session -d -P -F '#{session_id}' -s <name> -n _p)`, `P=` the placeholder's `@id`, `move-window -d -s <win @id> -t "$S:"`, `kill-window -t "$P"`, `move-window -r -t "$S"`, set `@parent` with `-t "$S:"`; the agent keeps running. Targets are ids only (see the naming rule). Check every session's windows first (`list-windows -a`): a thread tab can sit in a non-thread session (e.g. the owner's `main`) without `@thread` but with `@hsid`.
- **The caller's session** (what `@parent` records, and where `THREAD_TAB=1` puts the tab): the caller's session (`$TMUX_PANE`'s, i.e. `tmux display-message -p '#S'`). Not inside tmux (the Hermes desktop agent): the session of the owner's most recently active client (`tmux list-clients -F '#{client_activity} #{client_session}' | sort -rn | head -1`). `--session S` overrides. No client and no `--session`: refused. Never a session per card.
- `--card C`: slug or id, resolved by kanban; the window gets `@card=<id>`, the Hermes title is `<C> · <topic>`. Without it the title is `<topic>` and the window has no `@card`.
- **A thread is ALWAYS a branch of the Hermes session that invoked the skill**: `$HERMES_SESSION_ID` (set in every Hermes agent's environment). The branch is made OFFLINE by `scripts/fork.py` (Hermes's own `SessionDB`, run with Hermes's interpreter: same lineage as `/branch`, i.e. `parent_session_id` + `_branched_from`, system prompt and transcript copied, titled) and the window runs `hermes -p <profile> --resume <NEW id>`, waits for `ready`, then pastes the brief. The source is never resumed, attached to or ended, so a LIVE chat (the desktop one) gets no second client and no stray message. `--from SESSION_ID` branches from another session. `--new` (fresh session, renamed once its id appears) only when explicitly asked. `HERMES_SESSION_ID` empty and no `--from`: refused with a message, nothing opened. `fork.py <source-id> <title> [--profile P]` prints the new id (usable alone; `--profile` wins over an inherited `HERMES_HOME`).
- **Placement (tab mode only)**: `tmux new-window -a` right after the invoking agent's window (the window of `$TMUX_PANE` when it is in the target session; for the desktop caller, the session's first window), pushing the others right.
- `--brief TEXT` inline; `--brief -` stdin (quoted heredoc `<<'EOF'` so the shell expands nothing); `--brief-gz B64` = base64 of gzip, when your tool parameter is size-limited (`gzip -c f | base64`).
- `--profile` (default `bili`), `--cwd DIR` (default `$PWD`).
- Output, one line: `window=<session>:<topic> (@id) title='…' card=<id|-> session=<id> mode=…`.
- `thread.sh list`: every window marked `@thread`, across sessions (`session  topic  window-id  card`). **`list`/`state` only prove a window is tagged, not that it is a sound thread**: to answer "which threads are open", also check the invariant (each thread = its own tmux session named by `thread()` + `@hsid` that exists in `~/.hermes/profiles/<p>/state.db` with `ended_at` NULL + a start command `--resume <@hsid>`, never `--continue`) and flag drift: a thread with no `@hsid` (it may be a second client of another chat), an ended Hermes session, a session holding only an `@card` window. Use `thread.sh doctor` when present; by hand: `tmux list-windows -a -F '#{session_name}|#{window_id}|#{@thread}|#{@hsid}|#{@card}|#{pane_start_command}'` plus one `sqlite3` query per id. Report drift, then fix it as a separate step (the doctor's finding is the test of the doctor). `thread.sh close <topic> [--session S]` (see Closing a thread): kills that window only (the Hermes session stays); refused when the topic is open in more than one session and no `--session`.

## Rules

- **Open a thread only when the owner explicitly asks for one** ("abre uma thread", "thread", "tópico"). Never on the agent's own initiative, never as the way to run long work: that goes to subagents. A skill or brief that suggests a thread does not count as asking.
- **Uma thread começa em shape.** O brief colado em toda thread nova leva na frente uma linha mandando carregar a skill `shape` e registrar com `shape.sh emit request.received --shaping <topic>`. Por quê: regra do dono, o sistema TEM de experimentar; abrir uma thread já é começar um shape daquele contexto, e o domínio shape registra o shaping de cada thread. A linha some se o brief já cita shape ou com `--no-shape`.
- **Testing anything focus-driven never touches his server's focus either**: no `select-window` on the default tmux server, not even "and back"; simulate the event (call the hook's command with the arguments it would get) or use a private server (`TMUX_SOCKET`).
- **Never move the owner's focus: tabs open in the background with -d** (`new-window -d -a`; never `select-window`/`switch-client`; a restart is `respawn-window` alone). A thread must not take the owner off the window he is on.
- **A finished thread lights its tab until the owner enters it** (approved look: ` ✓ <topic> ` on a bordô `#800020` background, white bold; cleared by a `session-window-changed` hook when that window becomes active). Mark it only when the tab is not the owner's active one; the marking lives in skill `tmux`.
- **Opening a thread by hand: fork first, never resume the invoker.** Run `fork.py "$HERMES_SESSION_ID" '<card> · <topic>'` and resume the NEW id; `hermes --resume $HERMES_SESSION_ID` (or `--continue`) in another window makes that window a second client of the live chat: what it types lands there as user messages and `/branch` is refused mid-turn.
- **Check `thread.sh list` before opening by hand**: a thread a subagent or an earlier call already opened is easy to duplicate; two windows of one topic split the work.
- **Reordering tabs by hand keeps the focus**: `move-window -d`/`swap-window -d` only, and check `#{window_active}` is still the owner's window afterwards (a swap carries the active flag with it).
- **Never make the owner wait on the thread tooling.** If `thread.sh` cannot open the thread now (a bug being fixed, a timeout), start the same work at once another way (a subagent with the same brief, or the window opened by hand following the rules above) and say which; a thread queued behind a tooling fix is a stalled request.
- **Before opening a thread to fix something, check main for the fix already landed** (`git log -S'<symbol>' --oneline`, then the live behaviour): an earlier thread or session may have done it, and the new one then only confirms and reports.
- **The brief ends with "one topic only: do not continue the other subjects of this conversation"**: a branch carries the whole parent history and otherwise picks up its open threads.
- **A thread starts compacted on its own topic**: right after the branch is ready and before the work, run `/compress <the topic>` (Hermes's focus-topic compression keeps only what that topic needs). Until `thread.sh` does it itself, the brief's first instruction says "primeiro rode /compress focado neste tópico, se o contexto estiver grande": a branch of a long parent otherwise starts with hundreds of thousands of tokens of other subjects, slow and expensive.
- **Check `thread.sh open --help` before passing a new flag** (an option still being built, e.g. `--focus`): an unknown option refuses the whole open and the thread never starts; fall back to putting it in the brief.
- **A follow-up for a running thread goes into that thread, not a new one**: the owner's later requirement on the same topic is one message in its pane (`mux.sh fila`, or `tmux send-keys -t <session>:<topic> -l "<msg>"` then a separate `Enter`), opening "Bili, recado do Gabriel para <topic>:" and written as the requirement (what to include and where it lands, e.g. "entra no backbrief"), never his dictated words pasted raw. A second thread on the same topic splits the work.
- Never put a secret in a brief: it lands in the session history.
- **One name, the Value Object `thread`** (`thread()` in `thread.sh`): every thread/tab/session name passes through it: lowercase, accents folded (NFD via perl; macOS `iconv //TRANSLIT` mangles them), spaces and `-` kept, a dot becomes `-`, anything else becomes a space ("Sygnal 0.2" → `sygnal 0-2`; see the Naming rule under Doctor for why a dot is never kept). The same value is the tmux session, its tab, `@thread` and the Hermes title; a card's tab is the card title in lowercase. Renaming what is already open goes through the same function (source it: `eval "$(sed -n '/^thread() {/,/^}/p' thread.sh)"`), never a second hand-written slug rule. Every rename also sets `automatic-rename off` on the window, and the server runs `set -g automatic-rename off`: otherwise the running program renames the tab back (`python3.14`, `zsh`).
- **A name with a dot or space is never a tmux target** (old sessions may still carry a dot; `thread.sh doctor` flags them): `=sygnal 0.2:` parses the dot as a pane separator and the command hits ANOTHER window (a `kill-window` there killed a live agent). Capture ids at creation (`new-session -P -F '#{session_id} #{window_id}'`) and target `$N`/`@N` only; split lists on `|`, not spaces.
- Card, topic and session: no quotes, `$` or backslash (refused). One window per topic per session; a duplicate is refused.
- The cost clock follows the active window's `@card` first, then the session name (cost-track); that is why the card is set on the window.
- **Every thread window carries `@hsid=<the Hermes session id it runs>`**: the Hermes shell hooks run in the shared gateway, not in the tab, so they get no `$TMUX_PANE` and find the tab only by the payload's `session_id`. A window opened by hand gets `tmux set -w -t <win> @hsid <id>` too, or it never lights nor moves. Use the id format the hook sends (`local-…` from a fork); a window resumed with a `YYYYMMDD_…` id may not match it.
- **Restoring threads after the tmux server dies needs `@hsid`, not tmux-resurrect alone**: resurrect saves the
  running process's command line, and a Hermes tab's process is `node … ui-tui/dist/entry.js` (the `hermes` launcher
  hands off without the `--resume <id>` argument), so it would bring the tab back as a NEW conversation. Resurrect
  keeps no process alive either: the agent dies with the server; it only records layout, cwd and command. The id
  lives in `#{pane_start_command}` (`hermes -p bili --resume <id>`) and in the window's `@hsid`: a restore reopens
  each thread with `hermes -p <profile> --resume <@hsid>`.
- Readiness is polled on the pane (`ready`/`opus`/`sonnet`, 40 s max, `THREAD_READY_TIMEOUT`); on timeout the window stays open and the brief is not sent.
- **Indexes stay 1..N**: the tmux server runs with `set -g renumber-windows on` (in `~/.tmux.conf`), so closing a thread closes the gap; check it is on before relying on tab numbers (`tmux show -g renumber-windows`).
- **Adopting an existing session as a thread** ("usa a sesh que tava aberta como thread"): `move-window -d -a -s <old>:<win> -t <session>:1`, rename it to the topic, set `@thread`, `@card`, `@hsid` and `automatic-rename off`, then send it the new focus as one message. The old tmux session disappears with its last window; the Hermes session is untouched.
- **"Where is session X" / "reopen X": check it is really gone before reopening.** `#{pane_current_command}` shows `zsh` for a pane started as `zsh -c 'hermes …; exec zsh'` even while Hermes runs: look at `ps -axo pid,command | grep <hsid|title>` and `capture-pane -p -t @N` (a `ready` status line = alive). Usually the session exists and only the owner's switcher cannot reach it (a dotted name), so fix the name, not the process.
- **"Go to X" is the owner asking to move his focus**: `tmux switch-client -c <his most recent client> -t '$N'` (client from `list-clients -F '#{client_activity} #{client_name}' | sort -rn | head -1`; target the session id, never the name). Only on that explicit ask; otherwise the never-move-focus rule holds.
- Don't touch other windows; `TMUX_SOCKET` selects another tmux server (tests use a private one).

## Doctor

`thread.sh doctor [--json] [--verbose] [--profile P]` states the invariant of a thread and checks it. Why: the pieces of a thread (tmux session and options, the Hermes DB, the hooks) are loosely coupled and drift apart with no single owner; nobody notices until a tab does not light up or two clients write to one chat. It follows the `doctor` skill protocol: each finding has dimension (environment|architecture|behavior|observability|agent), check, status (ok|warn|drift|fail), evidence (the raw fact) and action (the exact fix, never run by the doctor). It detects and reports; the fix is separate. Read-only: it never kills, renames, moves or selects anything.

Invariant, per window with `@thread`:

- `thread-has-own-session` (environment): the tmux session is named like the thread and the thread is its window.
- `hsid-set` (observability): `@hsid` is set; without it the hooks cannot find the tab (no light, no sort).
- `hsid-in-db` (environment): that id exists in `~/.hermes/profiles/<profile>/state.db` (`THREAD_STATE_DB` overrides; no db = a warn, Hermes checks skipped).
- `hsid-live` (behavior): the session is not ended (`ended_at` NULL).
- `resume-hsid` (environment): the pane's start command is `--resume <hsid>`, never `--continue` (that makes a second client of someone else's chat).
- `card-not-a-session` (architecture): a session whose windows carry `@card` but no `@thread`: a card is a thread or a tab, never a session of its own.
- `viewer-path` (environment, warn): the pane runs `threadview.py` from another checkout.
- `name-targetable` (environment): no session or window name has a dot (any session, thread or not). tmux reads `a.b` in a target as `window.pane`, so `has-session`, `switch-client` and `sesh connect` fail with "can't find pane". The action is `tmux rename-session -t '$N' '<thread() value>'`.

**Naming rule (the Value Object `thread()`):** lowercase ASCII; spaces and `-` stay; accents are stripped; any other character becomes a space; **a dot becomes `-`, so a thread name never has a dot**: tmux reads the dot as the window.pane separator, so a session called `sygnal 0.2` cannot be reached by `has-session`/`switch-client`/`sesh connect` (the owner's cmd+o and cmd+l). `Sygnal 0.2` -> `sygnal 0-2`. Spaces are fine (`has-session -t 'a b'` works).

Text line: `<status> <dimension> <check> <session>/<window-id>: <evidence> -> <action>`, then `ok N threads` or `drift K of N`. `--json`: one object per finding (`dimension, check, status, session, window, evidence, action`). `ok` findings only with `--verbose`. Exit 0 healthy, 1 drift/fail, 2 the doctor could not run (no tmux server). Tests: `scripts/test-doctor.sh` (private tmux server, fake state.db).

Tests: `scripts/test.sh` (covers the tab mode; a test that sets `THREAD_TAB` must pass it inside the `run-shell` command, since `thread.sh` launched by `run-shell` sees the tmux server's environment, not the test's). Credits: [README.md](README.md). History: [CHANGELOG.md](CHANGELOG.md).

## The thread view (the owner talks through a screen)

When a message arrives as "[thread view] Gabriel digitou…", the screen (`view.py <sid> …`) is the only reply and the
turn has ~10 s.

- **The foreground call does only screen writes** (pulse, step, decision). Anything else, even `worker add` plus a
  tournament command, can pass 10 s: put `worker add <id>` as the FIRST command inside the background job, then the
  work, then `worker done|fail <id>`, so a done never targets a worker that was not registered. Launch it with the
  terminal tool's `background=true` (Hermes refuses `nohup`/`&` wrappers in a foreground command).
- **A pick by number ("segue com a 03") means the ranking shown at that moment**: read `get` (or the round's options)
  to map it to a name before acting, then speak of it by name; numbers move with every ranking.
- **Tournaments** (skill choice): a round after the first must include the standing champion. When the owner's
  feedback rules the champion out, keep it in the round last, with the lowest %, and lead with the option his words
  describe.

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

Applies where several threads share one session (`THREAD_TAB=1`, or a session that still holds thread tabs); with the
default one-session-per-thread there is nothing to sort inside a session, and the session list is the owner's
switcher. The order is an **MRU list** (most recently used first: the term of the cache literature, and the order of macOS's ⌘Tab), with an **attention band** in front. `thread.sh sort [<tab>] [--now]` applies it to the tab's session in one go: it computes the wanted order and moves only what is out of place.

1. **Tab 1 is the Bili** (the session's first window). **Windows without `@thread`** (zsh…) stay **last**, in their own order.
2. Between them, three bands: **needs the owner** (`@ask` ◆ open question, `@done` ✓ finished and not seen), then **working** (`@agent=working` or `@subagents` > 0), then **idle and seen**.
3. Inside a band, **the highest `@touched` first** (ms; ties keep the current order). `sort <tab>` stamps `@touched` on that tab when it is a thread.
4. **The owner's tab never moves**: it keeps its index and the focus (`move-window -d` around it).
5. **Debounce** of ~2 s (`THREAD_SORT_DEBOUNCE`, `0` = inline): a burst of events is one sort, so tabs do not jump on every hook. `--now` skips it.
6. **Numbers stay 1..N** (`move-window -r` at the end; `renumber-windows on` covers closes). Any code that moves tabs with `-a`/`-b` ends with `move-window -r -t =<session>`: those shift indexes up and leave gaps that `renumber-windows` (close-only) never fixes.
7. **Motion**: a tab that changes place slides there one `swap-window -d` step at a time (`THREAD_ANIM_MS`, default 45 ms; `0` = jump) and glows bordô (`window-status-style`) until ~0.6 s after it lands; when the owner's tab stands in the path it jumps over it in one move instead (a swap would move his tab). Prove motion on a private server (`TMUX_SOCKET`) by sampling `list-windows` every 20 ms while `sort --now` runs.

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
- **"Link X to this thread as the main resource"** = artifact `01` on the thread screen:
  `view.py <sid> artifacts '[{"key":"01","name":"<X> (recurso principal)","state":"ready","path":"<url or file>"}, …]'`
  (a URL works as `path`; the call rebuilds the HTML gallery). `artifacts` replaces the whole list, so re-list what
  should stay (a tournament redraws its own on the next round).
- **ctrl+l** shows the component names (Goal, Steps, Artifacts, Decision, Pulse, Queue, Input).
- Headless `--resume` on a long session makes Hermes compact it (old rows `active=0`); the live tab still holds the old
  history in memory, so don't type in both at once.

## Estado em tempo real

`thread.sh state [<aba>]` dá uma linha JSON por thread: sessão, índice, tópico, estado (`working` ●, `ask` ◆, `done` ✓, `idle`), subagentes, `touched` (ms) e cartão.

`thread.sh watch` imprime o estado atual e depois uma linha a cada mudança, ao vivo, do NATS local (`mesa.thread.state.changed`, `THREAD_NATS_URL`). O dev-console e a barra nativa assinam o mesmo assunto.

Evento na escrita, não consulta periódica: quem grava o estado (o `agent-state.sh` da skill tmux, e o `sort` ao reordenar) publica na hora, por `scripts/thread-state.sh`, que fala o protocolo do NATS direto no `/dev/tcp` do bash, sem abrir processo. Por que não o control mode do tmux (`refresh-client -B`, `%subscription-changed`): o man do tmux 3.7 diz que ele avisa "at most once a second", lento para a meta de 50 ms.

Medido (`scripts/test-state.sh`, tmux privado): da gravação à linha no watch, mediana de 33 a 53 ms com a máquina em carga 30 em 10 núcleos. Sem NATS no ar, o `state` funciona e o `watch` diz que não há fonte ao vivo.

