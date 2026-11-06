---
name: cost-track
description: >-
  Use when pricing where the owner's time goes: everything is monetary, everything has a cost. Every domain belongs
  to a cost center (a client with a day budget, or an investment with no budget but a cost), and a running clock in
  a domain becomes a time entry priced at what he is worth. Design stage, drawn in the dev-console as the Costs
  domain. Not task-understand (tasks) and not the dev-console's money bar code itself.
metadata:
  version: 0.2.0
---

# cost-track

**Design stage.** The domain is **Costs** (`/domain/costs` in the dev-console, "Biliboss Skills - Costs"); the code is
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

## Journal

Global and append-only, `~/.local/share/costs/events.jsonl` (override `COSTS_DIR`), a JSONL he may edit by hand while
prototyping. Hook it into the console: add `scripts/dev_console_project.py` to `~/.local/state/dev-console/domains.txt`.
