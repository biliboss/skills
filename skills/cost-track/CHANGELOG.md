# Changelog

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
