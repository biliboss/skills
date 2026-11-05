---
name: tasks
description: >-
  Design stage. A Task is explained to someone, and at the end that person repeats it back the way they
  understood it (teach-back), so the gap between what was meant and what was understood shows before the
  work starts. Use when the user says "tasks", "teach-back", "repete do jeito que entendeu", "explica a
  tarefa", "abre o tasks no dev-console". Not tensions (gaps between actual and desired reality) and not
  the Linear (the team's board).
metadata:
  version: 0.1.0
---

# Tasks

**One Entity:** Task, a piece of work explained to someone (the most universal name: a to-do at home, an
assignment at school, a ticket in a software team).
**Two events, in order:**

| Event | Command | What happened |
|---|---|---|
| `task.explained` | `explain` | someone explained the task, in their own way and with the time it needed |
| `understanding.taught_back` | `teach_back` | at the end, the receiver repeated it back the way they understood it |

The practice is **teach-back** (health literacy: "explain it back in your own words"); the loop it closes is
**closed-loop communication** (aviation, crew resource management). Use these names; do not invent others.

## Design stage

- The code is `scripts/tasks.py` (`EVENTS`, the projector `_project`, `TasksJournal`); the journal is
  `scripts/tasks.jsonl`, edited by hand while the domain is designed.
- The comment above each command in `EVENTS` is the event's description for humans (the dev-console shows it).
- See it in the dev-console: add `scripts/dev_console_project.py` to `~/.local/state/dev-console/domains.txt`
  and open `/domain/tasks`. Change events in `EVENTS`, never in the console.
