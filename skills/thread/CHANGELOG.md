# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

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
