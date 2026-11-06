# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-11-06

### Added

- `kanban.sh describe <card> --file <path>|--text <t>`: `card.described {text}`, the card's description (the 5-field request); the last one wins, an empty or identical text is refused. `show` prints it (and `description` in `--json`).
- The Quadro shows the description's first line ("Por quê: ...") under the title in the muted style; the card's sidebar History tab starts with the full text.

## [0.6.1] - 2026-11-06

### Changed

- `kanban.sh pull` opens the card's plan with `domain-plan` (`plan.sh start`, `plan` in the JSON; a missing skill is `null`, a failed start never fails the pull; `PLAN_SH` overrides the script in tests).

## [0.6.0] - 2026-11-06

### Changed

- The Quadro's "há N min na etapa" is static (drawn by the server, refreshed by the 10 s poll or any money event): time only moves where the clock runs, so only a card with `data-tick-rate` > 0 ticks R$ and time.
- `WATCH` in the project file: the console reloads on a change in cost-track's scripts.

## [0.5.0] - 2026-11-06

### Added

- `kanban.sh pull "<title>" [--domain] [--repo] [--context|--context-file] [--center] [--no-switch] [--swap] [--json]`: one gesture to start a piece of work: the card (reuse the open one with that slug, else create in Upstream; exit 5 `{"full": title}` when Upstream has no room, `--swap` sends the current card to Todo), the cost center binding, `hermes.sh workspace`, and the owner's tmux client switched. Identity is `slug(title)`. No new event.

## [0.4.2] - 2026-11-06

### Fixed

- A running entry written by tmux-focus (`driver: tmux`) is live without page pings (no 45 s staleness).

## [0.4.1] - 2026-11-06

### Added

- Policy: one card per piece of work the owner names; subagents and delegations create no card; delegating moves the work's card.

## [0.4.0] - 2026-11-06

### Added

- WIP limit per stage: `stage_limits` in the config, `{"Upstream": 1}` by default. `create --stage` and `move` refuse a full stage with exit 4, naming the card there; `--force` allows it and records `forced: true`.
- The Quadro's column header and `kanban.sh list` show `count/limit` (`Upstream 1/1`); over the limit the header is bold with a darker rule.

### Changed

- `create` defaults to Todo (was Upstream).

## [0.3.0] - 2026-11-06

### Added

- `kanban.sh top <card>` and `rank <card> <position>`: event `card.prioritized {position, stage}`; the top of a column is the card in focus, ranked cards come first, the rest by arrival, a move clears the rank.
- `kanban.sh rename <card> <title>`: event `card.renamed {title}`.
- Stage `Todo`, the first one (the backlog); its time is not Upstream money. `create` still defaults to Upstream.
- The Quadro counts the time in the stage up every second in the browser (`data-since`), with the cost clock's rate, and redraws by itself within ~2 s of a change to the journal (`JournalStamp`); four columns.
- `test_dev_console_project.py`: the rendered data attributes, the stamp and the order.

## [0.2.0] - 2026-11-06

### Added

- `kanban.sh wip [--repo R]`: open PRs per repo against the WIP limit (`wip.limit`, default 3, `~/.config/kanban/config.json`); exits 3 at or over it.
- `kanban.sh sweep [--hours 48] --repos a/b,c/d [--apply]`: PRs and branches older than N hours; `--apply` closes PRs whose content is already in main, deletes remote branches already in main, and records the rest.
- Events `item.aged` `{repo, kind, ref, age_h}` and `decision.requested` `{text, repo, ref, reason}` (no card); a deploying repo (viacorretor) only ever gets `decision.requested`.

## [0.1.0] - 2026-11-06

### Added

- The Kanban domain: `card.created` and `card.moved` in a global append-only journal (`~/.local/share/kanban/events.jsonl`, override `KANBAN_DIR`); a Card has a title, a dev-console domain and a stage (Upstream, Downstream, Feito).
- `scripts/kanban.sh` (logic in `kanban.py`, uv, stdlib only): the journal's only writer (`create`, `move`, under a file lock) and its reads (`list`, `show`, `money`, each with `--json`).
- The value objects (`Stage`, `NewCard`, `Move`, `Stay`, `Card`, `TimeEntry`, `Slice`, `Money`, `CardMoney`, `UpstreamTotals`, `Column`, `Board`) and the pure functions that compute them from the Kanban and Costs journals: a card's time clipped to its Upstream stays and priced at its cost center's hour rate; the band for today, the week (from Monday) and the month. The Costs journal is only read.
- The dev-console project: the Quadro module, the console's home (`CONSOLE_HOME`), with the money band ticking every second while the clock runs on the domain of a card in Upstream; the card's sidebar (Histórico, Tempo, JSON); widgets Board, UpstreamBand, CardHistory, CardTime.
- `scripts/test_kanban.py` (stdlib unittest): the Upstream clipping, the stopped entry's real start, the running and stale stretches, the band's periods, the journal and the CLI.
