---
name: kanban
description: >-
  Use when the owner's work moves across his Kanban board (Upstream, Downstream, Feito), each card tied to a
  dev-console domain, or when he asks what a card or the Upstream work cost. The only writer of the Kanban journal
  (`kanban.sh create`, `move`), drawn in the dev-console as the Kanban domain whose Quadro module is the console's
  home, with a money band (today, week, month) priced from the Costs journal. Use when he says "cria um card",
  "move o card", "manda para Downstream", "o que está em Upstream", "quanto custou esse card", "mostra o quadro",
  "quadro kanban". Not backbrief (a task explained and taught back) nor cost-track (the clock and the cost centers).
metadata:
  version: 0.4.0
---

# kanban

The domain is **Kanban** (`/domain/kanban` in the dev-console, "Biliboss Skills - Kanban"); the code is
`scripts/kanban.py` (`EVENTS`, `TRANSITIONS`, the value objects, the pure functions, the journal, the CLI) and
`scripts/dev_console_project.py` (the widgets, which only draw what `kanban.py` returns). The names come from the Kanban
Method (David J. Anderson, 2010) and Upstream Kanban (Patrick Steyaert, 2018): the commitment point splits the board,
upstream the options still being discovered, downstream the work committed to.

**Entity:** Card: a title, the dev-console domain it belongs to (its slug), and its stage, `Todo` | `Upstream` |
`Downstream` | `Feito`. UI text is Portuguese; this file and the code comments are English.

| Event | Command | Value object | What happened |
|---|---|---|---|
| `card.created` | `create` | `NewCard {title, domain, stage}` | a card entered the board (in Upstream unless told otherwise) |
| `card.moved` | `move` | `Move {stage, previous}` | the card changed stage, in any direction (back to Upstream too) |
| `card.prioritized` | `top`, `rank` | `Prioritize {position, stage}` | the owner ordered the stage's queue: the card sits at `position` (0 = top) |
| `card.renamed` | `rename` | `Rename {title}` | the card got another title |
| `item.aged` | `sweep --apply` | `{repo, kind pr\|branch, ref, age_h}` | an open PR or a branch is older than N hours (48) and not in main; no card |
| `decision.requested` | `sweep --apply` | `{text, repo, ref, reason}` | only the owner decides: a merge that publishes (the repo's main deploys), a branch with work outside main |

The descriptions for humans are the comments on each command in `EVENTS`.

## The one writer

`scripts/kanban.sh` (`kanban.py`, uv, PEP 723, stdlib only) is the only writer of the journal. Use it when Gabriel asks
("cria um card para X no domínio Y", "move o card X para Downstream"); the board in the console only reads.

```sh
scripts/kanban.sh create "<title>" --domain <slug> [--stage Todo|Upstream|Downstream|Feito] [--force] [--actor <who>]
scripts/kanban.sh move <card> <stage> [--force] [--actor <who>]   # exit 4 if the stage is full; <card>: its id, a unique start of it, or its exact title
scripts/kanban.sh top <card> [--actor <who>]            # to the top of its stage: the card in focus now
scripts/kanban.sh rank <card> <position> [--actor <who>]  # to a place in its stage's queue (0 = top)
scripts/kanban.sh rename <card> <title> [--actor <who>]
scripts/kanban.sh list [--stage <stage>] [--json]       # the cards, per stage, with their Upstream money
scripts/kanban.sh show <card> [--json]                  # its stays, its Upstream slices of time, the total
scripts/kanban.sh money [--json]                        # the band (Hoje, Semana, Mês) and each card's total
scripts/kanban.sh wip [--repo owner/name] [--json]      # open PRs vs the WIP limit; exit 3 at or over it
scripts/kanban.sh sweep [--hours 48] --repos a/b,c/d [--apply] [--json]
```

**WIP limit.** `wip.limit` (default 3) in `~/.config/kanban/config.json` (override `KANBAN_CONFIG`;
`wip.repos {"owner/name": n}` per repo). `wip` counts the repo's open PRs with `gh pr list` and exits **3** at or over the
limit (1 when gh fails: an unknown count is not "over"). Run it before opening a PR (backbrief step 9);
`hermes.sh spawn hacker ... --repo R` runs it and refuses (exit 6).

**Aging sweep (daily).** `sweep` lists the open PRs (by creation) and branches (by last commit) older than `--hours`
(48). Without `--apply` it only reads. With `--apply`: a PR whose content is already in main (same commits, or every
changed file identical on main, so squash merges count) is closed with a comment, a remote branch already in main is
deleted, and the rest is recorded once per 24 h: `item.aged`, plus `decision.requested` for a branch with work outside
main. It never deletes unmerged work and never merges. A repo whose main deploys (`viacorretor/*`, `*/the-viacorretor`)
gets only `decision.requested`, never a close or a delete. Tests override gh with `KANBAN_GH`.

`create` and `move` print the event they appended. The journal is global and append-only,
`~/.local/share/kanban/events.jsonl` (override `KANBAN_DIR`), one line per event
`{"id","event","at","actor","card_id","value"}`, written under a file lock. It refuses an unknown event, a card with no
title or no domain slug, an unknown stage (any case is accepted: `feito`), a move to the stage the card is already in,
and an unknown or ambiguous card (it lists the matches). Never edit the real journal by hand while the console reads it.

## The WIP limit of a stage

**Upstream holds one card** (Kanban Method: a WIP limit per column, an explicit policy). `create --stage` and `move`
refuse a card into a full stage with exit 4 and name who occupies it: `Upstream está cheio (1/1): Via Blog. Mova-o antes,
ou use --force para registrar a exceção.` `--force` lets it in and records `forced: true` in the event's value. The limits
live in `~/.config/kanban/config.json` (override `KANBAN_CONFIG`): `"stage_limits": {"Upstream": 1}` is the default;
other stages are unlimited unless set, `0` lifts one. The Quadro's column header and `kanban.sh list` show `count/limit`
(`Upstream 1/1`); over the limit the header goes bold with a darker rule (grayscale, no red). `wip.limit` (open PRs per
repo) is a separate limit.

## The order of a column

**The top of a column is the card in focus** (Kanban literature: ordering the queue by priority). A stage's cards follow
the latest explicit order (`top`, `rank`, replayed from `card.prioritized`); cards never ranked come after the ranked
ones, by arrival. Moving a card to another stage clears its rank there. **Todo** is the backlog, what is not being worked
now: its time is waiting, not discovery, so it never counts as Upstream money (`create` defaults to Todo).

**The Quadro is live.** It counts up in the browser every second from the server's `since` (the time in the stage) and
`tick-rate` (the cost clock's R$ per hour), without a reload, and redraws by itself within ~2 s of any change to the
journal (a tiny `JournalStamp` widget answers the journal's mtime; the board is fetched again when it differs). The
server stays the source of truth at each redraw.

## The money rule

The Kanban reads the Costs journal through cost-track's `scripts/costs.py` (`events()`, `running()`, `centers()`,
`rate_hour()`), loaded by path from the sibling skill, and never writes it.

- **A time entry** is a `time_entry.stopped` of a domain. It runs from its `time_entry.started` (same center and domain)
  for its `seconds`: its own `at` is when it was written, which is later than its end after an idle trim or a quiet
  page. The stretch running now (`running.json`) runs until now; one nobody pinged for 45 s ended at its last ping (the
  console's own `_settle` rule, read here, never applied).
- **A card's money** is the time entries of the card's domain clipped to the card's Upstream stays: from its
  `card.created` in Upstream, or a `card.moved` into Upstream, to the next move out (now while it is still there). Time
  before, between and after those stays does not count; a partial overlap is clipped. Each slice is priced at the hour
  rate of the entry's cost center (`rate_hour`: a client at `value_month`, an investment at `goal_month`, the R$ 50 mil
  goal), rounded to cents. The center is the one the entry was billed to, which is the domain's even when only a project
  file declares it (`COST_CENTER`).
- **The band** sums the cards' Upstream time for **Hoje** (from local midnight), **Semana** (from Monday 00:00) and
  **Mês** (from the 1st), up to now, in R$ and hours. A second of the clock counts once: two cards of one domain in
  Upstream at the same time each show it whole, the band counts it once.
- **Live:** while the clock runs on the domain of a card that is in Upstream, the band and that card gain the center's
  rate per hour. The screen ticks every second from the server's snapshot (the money bar's way) and redraws every 10 s
  and at once when the money bar starts, stops or enters (`devconsole-money` on `document`).
- **The price is today's** rate of the center, as the owner asked ("priced at the hour rate of the domain's cost
  center"). Costs' own entries keep the rate they were recorded at, so after a `worth.updated` the board re-prices the
  past and the money bar does not.

## Value objects

Frozen dataclasses in `kanban.py`, defined before any screen: `Stage` (enum), `NewCard`, `Move`, `Stay`, `Card`,
`TimeEntry`, `Slice`, `Money`, `CardMoney`, `UpstreamTotals`, `Column`, `Board` (`VALUES` says which event carries which).
The pure functions take journal events and a `now` and return them: `card_from`, `cards_from`, `time_entries`,
`upstream_spans`, `card_money`, `periods`, `upstream_totals`, `board`. `read_board()` and `read_card()` read both
journals and call them. The widgets and the CLI draw only these, so the screen, `kanban.sh money` and the tests agree.

## In the dev-console

- **The Quadro is the console's home.** `TABS = ["Quadro"]`, `MODULE_WIDGETS = {"Quadro": ("card.created", "Board")}`
  and `CONSOLE_HOME = "Quadro"`: `/` opens it when the journal has a card (else the first domain, as before); ⌘P lists it
  (`g q`). The status line is the console's: `Biliboss Skills - Kanban · Quadro · money bar`.
- **The board**: the money band on top, then Upstream, Downstream and Feito; each card shows its title, its Upstream
  money (R$ and hours), how long it has been in its stage, and its domain; cards in the order they arrived in the stage.
  Read only: no drag, no button that writes.
- **A click on a card** (Enter, Space) opens the console's contextual sidebar: `ENTITY_PARTS = {"Histórico":
  "CardHistory", "Tempo": "CardTime"}`, then its JSON; `?ent=<card id>` keeps it open across a reload, Esc closes it.
- **Widgets**, each with its title: Board (part UpstreamBand), UpstreamBand, CardHistory and CardTime on `card.created`
  (the event every card has, so the sidebar can render them for any card); CardHistory on `card.moved`.
- `COST_CENTER = "biliboss-skills"`: the house's own work, an investment priced at the goal.

## Setup (once, by the owner)

```sh
# the first card
scripts/kanban.sh create "Kanban" --domain kanban --actor gabriel
# the kanban domain in an investment cost center: restate the center's latest value with kanban in its domains
# (see it with: grep '"biliboss-skills"' ~/.local/share/costs/events.jsonl | tail -1)
../cost-track/scripts/costs.sh emit cost_center.updated '{"text": "O Biliboss Skills é investimento: os domínios da casa (Tasks, o dev-console, Tensions, o Kanban) entram nele.", "name": "Biliboss Skills", "kind": "investment", "domains": ["tasks", "dev-console", "tensions", "kanban"]}' --cost-center biliboss-skills --actor gabriel
# the domain in the console's registry; a running console picks it up by itself
../dev-console/scripts/console.sh domains add scripts/dev_console_project.py
```

Tests: `uv run --script scripts/test_kanban.py` (temp `KANBAN_DIR` and `COSTS_DIR`, invented data). Check a change on a
second console (another port, `DEV_CONSOLE_REGISTRY=<empty file>`, temp `KANBAN_DIR` and `COSTS_DIR`), never the real
journals.
