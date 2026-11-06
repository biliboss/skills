# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added

- `plan.sh start | add | show | drift | confirm`: the plan as a hand-editable JSONL in `<repo>/.plan/<slug>.jsonl`
  (`plan.started`, `element.updated` of kind event, screen or document, `plan.confirmed`).
- `drift`: the drawing against the `EVENTS` of the code (read with `ast`) and the screens' files or URLs: to build, built
  (`--mark` turns it real), unplanned, and lost; `--detailed-exitcode` exits 2 on drift.
- `plan.sh sync` and `--console-source`: the real events file plus the drafts, each commented as a draft, written as the
  dev-console's SOURCE (it reads EVENTS with ast), so a draft shows outlined = not in the code.
- `dev_console_plan.py`: the drafts' edges for `TRANSITIONS`, and the widgets Plano (the drift) and Tela (the screen above an event).
