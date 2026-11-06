# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-11-06

### Changed

- Questions through `interview`; event names from the wiki transitions; screens in `.plan/<slug>/telas/`; the version's LP; an empty domain takes the console down; drift counts a screen as built when its file exists.

## [0.2.0] - 2026-11-06

### Changed

- Pin the outcome (wiki on `origin/main`, one question) before drawing; Upstream writes no product code.

## [0.1.0] - 2026-11-06

### Added

- `plan.sh start | add | show | drift | confirm`: the plan as a hand-editable JSONL in `<repo>/.plan/<slug>.jsonl`
  (`plan.started`, `element.updated` of kind event, screen or document, `plan.confirmed`).
- `drift`: the drawing against the `EVENTS` of the code (read with `ast`) and the screens' files or URLs: to build, built
  (`--mark` turns it real), unplanned, and lost; `--detailed-exitcode` exits 2 on drift.
- `plan.sh sync` and `--console-source`: the real events file plus the drafts, each commented as a draft, written as the
  dev-console's SOURCE (it reads EVENTS with ast), so a draft shows outlined = not in the code.
- `dev_console_plan.py`: the drafts' edges for `TRANSITIONS`, and the widgets Plano (the drift) and Tela (the screen above an event, in a sandboxed iframe: a file only from inside the repo, a URL only http(s)).
