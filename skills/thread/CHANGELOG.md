# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

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
