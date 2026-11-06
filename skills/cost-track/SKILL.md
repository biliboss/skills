---
name: cost-track
description: >-
  Use when pricing where the owner's time goes: everything is monetary, everything has a cost. Every domain belongs
  to a cost center (a client with a day budget, or an investment with no budget but a cost), and a running clock in
  a domain becomes a time entry priced at what he is worth. The only writer of the Costs journal (`costs.py emit`),
  drawn in the dev-console as the Costs domain; the console's money bar reads and writes it through this file. Not
  backbrief (tasks).
metadata:
  version: 0.4.2
---

# cost-track

The domain is **Costs** (`/domain/costs` in the dev-console, "Biliboss Skills - Costs"); the code is
`scripts/costs.py` (`EVENTS`, `TRANSITIONS`, the projector, the journal) and `scripts/dev_console_project.py`.

**Entity:** CostCenter (accounting's term). **Value:** TimeEntry (the timesheet's term), one focus stretch.

| Event | Command | What happened |
|---|---|---|
| `worth.updated` | `update` | he said what he is worth: the value now (R$ 20 mil/month), the goal (R$ 50 mil) and the paid hours per day |
| `cost_center.updated` | `update` | a cost center was created or changed: a client that pays (day budget) or an investment (priced at the goal) |
| `time_entry.started` | `start` | the clock started in a domain, counting for its cost center |
| `time_entry.stopped` | `stop` | the clock stopped; the stretch is an entry with seconds, the hourly rate used and the cost in R$ |

The descriptions for humans are the comments on each command in `EVENTS`. The rule behind it: a client is charged at
the current value and has a day budget (`pays_month / work_days_month`); an investment is charged at the goal price
and has no budget; each entry stores the rate it used, so a later price change never rewrites the past.

**One timer, checked in a microsecond.** Gabriel's time is one: at most one entry runs, in `~/.local/share/costs/running.json`, which exists only while it runs. `costs.sh running` (or `[ -e ~/.local/share/costs/running.json ]`) answers without uv: exit 0 and the JSON, or exit 1. Every start replaces the running entry; nothing keeps a second one.

## The one writer

`scripts/costs.py` is the only writer of the journal (stdlib only, run through `scripts/costs.sh`):

```
scripts/costs.sh  emit <event> '<json value>' --cost-center <id> --actor <who>
```

It appends one line (id and `at` generated; `worth.updated` needs no center, every other event does). The module API
the dev-console imports: `worth()` (latest `worth.updated` value), `centers()` (latest value per center),
`center_of(slug, declared=None)` (the `COST_CENTER` a project declares, else the center whose `domains` lists the
slug, else `None`), `rate_hour(center)` (a client at `value_month`, an investment at `goal_month`, over
`paid_hours_day × work_days_month`), `budget_day(center)` (client only: `pays_month / work_days_month`) and
`today(center)` (seconds and cost of today's `time_entry.stopped`). Tests: `uv run --script scripts/test_costs.py`.

A domain joins a center with `COST_CENTER = "<id>"` in its project file, or by being in the center's `domains` list in
`cost_center.updated`. The Costs domain itself declares `biliboss-skills`.

## The clock follows tmux

The clock has ONE writer besides manual commands: `costs.sh tmux-focus <session|->`, run by tmux hooks (`costs.sh tmux-install`
puts them in `~/.tmux.conf`; `tmux-uninstall` removes; `costs.sh status` shows the running entry). Attached to (or switched by
sesh to) a session named like an open Kanban card (Upstream/Downstream; slug of its title or its domain) starts an entry in that
card's domain (card id in the value); any other session or a detach stops it. Closing a session = losing focus. Idempotent, silent.

## Widgets

On the journal's real data, each starting with its title: **Worth** (the hour now and at the goal, per min and month),
**CostCenters** (each center, kind, day budget or "sem teto", cost), **DayCost** (`HOME`: today per center with hours,
cost, "de R$ <budget>" or "investido", red over budget, and the total), **TimeEntries** (each stretch as its sentence)
and **CostToolbar** ("Relógio de custo": the console's real money bar as an `Iframe` of `?embed=money`, `fake = True`;
never a copy of the bar). A new event worth seeing gets its widget in the same change as the event.

## Journal

Global and append-only, `~/.local/share/costs/events.jsonl` (override `COSTS_DIR`), a JSONL he may edit by hand while
prototyping. Hook it into the console: add `scripts/dev_console_project.py` to `~/.local/state/dev-console/domains.txt`.
