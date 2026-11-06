# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added

- The Kanban domain: `card.created` and `card.moved` in a global append-only journal (`~/.local/share/kanban/events.jsonl`, override `KANBAN_DIR`); a Card has a title, a dev-console domain and a stage (Upstream, Downstream, Feito).
- `scripts/kanban.sh` (logic in `kanban.py`, uv, stdlib only): the journal's only writer (`create`, `move`, under a file lock) and its reads (`list`, `show`, `money`, each with `--json`).
- The value objects (`Stage`, `NewCard`, `Move`, `Stay`, `Card`, `TimeEntry`, `Slice`, `Money`, `CardMoney`, `UpstreamTotals`, `Column`, `Board`) and the pure functions that compute them from the Kanban and Costs journals: a card's time clipped to its Upstream stays and priced at its cost center's hour rate; the band for today, the week (from Monday) and the month. The Costs journal is only read.
- The dev-console project: the Quadro module, the console's home (`CONSOLE_HOME`), with the money band ticking every second while the clock runs on the domain of a card in Upstream; the card's sidebar (Histórico, Tempo, JSON); widgets Board, UpstreamBand, CardHistory, CardTime.
- `scripts/test_kanban.py` (stdlib unittest): the Upstream clipping, the stopped entry's real start, the running and stale stretches, the band's periods, the journal and the CLI.
