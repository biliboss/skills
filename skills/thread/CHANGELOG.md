# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-11-06

### Changed

- A thread opens **the thread agent** by default: the same offline branch (fork.py), run headless, with the tab running the thread view (`threadview.py <new id>`) and the brief as the first message of its queue (no paste, no waiting for the Hermes TUI). `--cli` (or `THREAD_UI=cli`) keeps the Hermes CLI; `--new` always uses it.
- SKILL.md: the thread shape (goal, steps, artifacts, decision, pulse, workers) written as the model's contract.
- Stage (Upstream → Downstream): every thread is born from the template in progress in the Upstream; `view.py stage upstream done` checks it and starts the Downstream; `stage downstream done` ends it. Drawn as one strip at the top.
- 20/80 screen: done steps collapse to one line, the step that moves or blocks shows whole with its note; an empty section is not drawn; the pulse is one line; the view draws at most 88 columns (a third of the screen, `THREADVIEW_WIDTH`).

- The lane's state comes from the screen: with a decision open it reads `◆ esperando você` (bordô), never "em progresso"; Agentes shows the Hermes subagents of the thread's tab (`@subagents`) besides the workers, and the prompt says that Downstream in progress means someone working, registered there.

- The Upstream's goal is to be ready for the Downstream: `view.py stage ready <0-100>` (in the template, 0 at birth), drawn as `UPSTREAM 70% pronto ▰▰▰▰▰▰▰▱▱▱`; 100 marks it ready and the owner moves it (D). Only the owner moves a thread to the Downstream (`--by owner`); the agent is refused.
- Agentes shows N subagents in parallel, one line each, read from Hermes's `async_delegations` of the thread's session (a batch "N parallel subagents: a; b" becomes N lines; done ones stay 15 s). `THREADVIEW_DB` points it at another database (tests).
- Related (part of the template): artifacts that are not images (the skill, the domain, the PR, the card) are link lines.
- The stage line is the first line; the subtitle keeps its indent; a decision is only for when the thread waits for the owner.

- The view state is closed as a value object (`scripts/view_state.py`: Goal, Stage with the Definition of Ready, Step, Artifact, Decision, Worker, and `check`); `view.py` refuses any write outside the shape; `view_state.py check <view.json>` validates a file.
- Definition of Ready: `view.py stage check add "<item>"` / `check <n> done`; the % ready comes from the list, drawn under the stage line while in the Upstream.
- Grayscale with one accent (a lighter bordô, `#c4405e`) for what moves or waits for the owner; hierarchy from weight, type and space.
- The Definitions of Ready are a catalog the agents improve from use, `templates/ready.json`: `base` (the domain drawn in the dev-console, the widgets of each event, the backbrief confirmed) at every thread's birth, plus one list per kind of work (`tui`, `web`) added with `view.py stage check template <kind>`.
- The shape line (`--no-shape` opts out) now reaches the thread view's queue too: it is applied before either path takes the brief.

### Fixed

- `i` (answer something else) no longer hides the open decision; only a decision edge answers it.

## [0.9.0] - 2026-11-06

### Added

- Every new thread's brief is prefixed with one line telling the agent to start by the `shape` skill (`shape.sh emit request.received --shaping <topic>`), unless the brief already mentions shape or `--no-shape` is passed. Tests cover the prefix and both opt-outs.

## [0.8.0] - 2026-11-06

### Added

- `thread.sh state [<tab>]` and `thread.sh watch`: the threads' state as JSON lines, live from the local NATS (`mesa.thread.state.changed`); `scripts/thread-state.sh` publishes on write (bash `/dev/tcp`, no process); `scripts/test-state.sh`.
- Fixed: the tab slide used `swap-window -d`, which on tmux 3.7 made the moved tab current (stole the owner's focus); now without `-d`.

## [0.7.0] - 2026-11-06

### Added

- `scripts/threadview.py`: the thread view, a fullscreen TUI where the agent builds the thread's screen and the input is a queue (received, read, timer, what changed); 10 s per turn with an overrun log; Agentes queue; choices and tournaments (skill `choice`) in the input; showcase in the dev-console.
- `scripts/view.py`: the agent's only output, the screen (goal, steps, artifacts, decision with confidence %, pulse, workers) and the HTML showcase.

## [0.6.0] - 2026-11-06

### Added

- `thread.sh sort [<tab>] [--now]`: tab order as an MRU list with an attention band (◆/✓ first, then working, then idle; MRU by `@touched` inside each band); the owner's tab is pinned; debounced ~2 s; numbers 1..N. `scripts/test-sort.sh`.

### Changed

- `thread.sh touch <tab>` is now `sort <tab> --now` (the thread no longer always jumps to tab 2: it goes to its band).

## [0.5.0] - 2026-11-06

### Added

- Closing a thread (SKILL.md): `thread.sh close --self --summary TEXT` for a delivered task thread; `close <topic> [--by owner|bili] [--summary]`; deferred when the owner is on the tab (`sweep`, also run by `touch`); one log line per close in `~/.local/state/threads.log`; refused while `@subagents` > 0. The brief ends with the self-close instruction.

## [0.4.0] - 2026-11-06

### Added

- `thread.sh touch <tab>`: a thread becomes tab 2 (the session's first window, the Bili, stays tab 1; windows without `@thread` stay at the end). Never takes the owner's focus (`move-window -d`; when he is on that very tab, the tabs in front of it move behind it instead). One list, O(windows), no sleep. Called by the tmux skill's `agent-state.sh` on a prompt and on the end of a turn.

## [0.3.1] - 2026-11-06

### Fixed

- `fork.py` copied the source's `source` label; for a gateway-owned chat that is `local`, which the gateway cannot adopt on resume (`not_found` in the TUI, the brief left queued). The branch now carries an adoptable label (`cli`, as `/branch`).

### Added

- Rule + test: the owner's focus never moves (windows open with `-d`; the active window is unchanged after `open`).

## [0.3.0] - 2026-11-06

### Fixed

- Branching no longer resumes the invoking session in a TUI. When that session was live (the desktop chat) the window became a second client of it: what was typed arrived as a user message in the live chat and `/branch` was refused mid-turn.

### Changed

- `scripts/fork.py` makes the branch offline through Hermes's own `SessionDB` (same lineage as `/branch` and the API's `/fork`: parent id, `_branched_from`, system prompt, transcript, title) and never ends the source. The window resumes the NEW session and the brief is pasted after `ready`.

## [0.2.0] - 2026-11-06

### Changed

- The tab opens in the tmux session where the skill was invoked (`$TMUX_PANE`'s), or, outside tmux, in the session of the most recently active client; `--session S` overrides. A session per card is never created.
- A thread is always a `/branch` of the Hermes session that invoked the skill (`$HERMES_SESSION_ID`, `--from ID` overrides): the window starts `hermes --resume`, waits for `ready`, sends `/branch <title>`, waits for `branched`, then pastes the brief. `--new` only when asked; with no session id and no `--from` it refuses.
- The tab opens right after the invoking agent's window (`new-window -a`; the session's first window for a desktop caller), so the newest thread is tab 2.
- Signature: `thread.sh open <topic> [--card C] [--session S] [--branch FROM_TITLE | --new] [--brief ...]`. Hermes title `<card> · <topic>` with a card, else `<topic>`. The card (slug or id, via kanban) is the window option `@card`; the window also has `@thread`.
- `thread.sh list` lists windows with `@thread` across sessions; `thread.sh close <topic> [--session S]` kills only that window.

## [0.1.0] - 2026-11-06

### Added

- `thread.sh open|list|close`: a card's topic thread in one call (tmux window + Hermes `/branch` or new session named `<card> · <topic>`), brief inline by argument, stdin or gzip+base64, pasted with bracketed paste.
- Tests with a fake `hermes` and a private tmux server.
