# Changelog

## [0.5.1] - 2026-11-06

### Changed

- Client contracts: `hours_day`, manual time pairs, `costs.sh bind`, and the finance report (`references/company-finance.md`).

## [0.5.0] - 2026-11-06

### Changed

- The clock reads the card from the ACTIVE WINDOW's `@card` first (a card id or prefix, open Upstream/Downstream), then falls back to the session name. The hooks pass `#{session_name} --card=#{@card}`; `tmux-focus`/`simulate` accept `--card=<id>`; the `hook` and `decision` log lines carry `window_card`.
- New hook `session-window-changed` (alongside `client-session-changed`, `client-attached`, `client-detached`): a window change inside one session moves the clock. Re-run `costs.sh tmux-install` to get it.

## [0.4.1] - 2026-11-06

### Added

- `costs.py bind <center> <domain>` (and `costs.bind`): binds a domain to a cost center with one `cost_center.updated` (the center's last value plus the domain in `domains`; none when already bound; the domain leaves any other center).

## [0.4.0] - 2026-11-06

### Added

- `costs.sh tmux-focus <session|->`, `tmux-install`, `tmux-uninstall`, `status` (`scripts/tmux_focus.py`): the cost clock follows the tmux session the owner is attached to; a session named like an open Kanban card runs the clock in the card's domain (card id in the entry), any other session or a detach stops it. Hooks `client-session-changed`, `client-attached`, `client-detached` (indexed, marked block in `~/.tmux.conf`). Tests in `scripts/test_tmux_focus.py`.

### Changed

- The tmux hooks are the only writer of the clock (the DevConsole window no longer drives it, see dev-console 0.29.2).

## [0.3.2] - 2026-11-06

### Changed

- Mentions `backbrief` (renamed from task-understand).

## [0.3.1] - 2026-11-06

### Changed

- `scripts/costs.sh` is the entry point (`uv run` behind it); the docs call it instead of `uv run --script scripts/costs.py`.

## [0.3.0] - 2026-11-05

### Added

- `scripts/costs.py` is the only writer of the Costs journal: the CLI `emit <event> '<json>' --cost-center <id> --actor <who>` (id and `at` generated) and the module API the dev-console imports: `worth()`, `centers()`, `center_of(slug, declared)`, `rate_hour(center)`, `budget_day(center)`, `today(center)`.
- `scripts/test_costs.py` (stdlib unittest): the rates of a client and an investment, the budget, the center of a domain by declaration and by `domains`, today's sum, a price change not rewriting the past, the CLI.

### Changed

- The journal folder is read from `COSTS_DIR` on every call (`journal_path()`), no longer once at import.

## [0.1.0] - 2026-11-05

### Added

- The Costs domain in design stage: `worth.updated`, `cost_center.updated`, `time_entry.started`,
  `time_entry.stopped`, drawn in the dev-console from `scripts/costs.py`; the journal is a global JSONL.
