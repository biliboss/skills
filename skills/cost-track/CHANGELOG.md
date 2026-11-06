# Changelog

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
