---
name: task-understand
description: >-
  One command, /task-understand, runs the whole workflow of the Tasks domain (design stage). A Task is explained to someone, and at the end that person repeats it back the way they
  understood it (teach-back), so the gap between what was meant and what was understood shows before the
  work starts. Use when the user says "task-understand", "teach-back", "repete do jeito que entendeu", "explica a
  tarefa", "vou te passar uma tarefa". Not tensions (gaps between actual and desired reality) and not
  the Linear (the team's board).
metadata:
  version: 0.3.0
---

# task-understand

One command runs the whole workflow, from `task.explained` to `understanding.taught_back`. The domain is
**Tasks** (plural: the set of tasks), shown in the dev-console as Biliboss Skills - Tasks at `/domain/tasks`;
other workflows of the domain come as `task-<action>` skills.

**One Entity:** Task, a piece of work explained to someone (the most universal name: a to-do at home, an
assignment at school, a ticket in a software team).
**Two events, in order:**

| Event | Command | What happened |
|---|---|---|
| `task.explained` | `explain` | someone explained the task, in their own way and with the time it needed |
| `understanding.taught_back` | `teach_back` | at the end, the receiver repeated it back the way they understood it |

The practice is **teach-back** (health literacy: "explain it back in your own words"); the loop it closes is
**closed-loop communication** (aviation, crew resource management). Use these names; do not invent others.

## Input

What reaches the agent when someone explains a task is a value object, and its contract is
`scripts/input.py`: User Prompt, Skill and Session Context (System Prompt, History, Memory, Environment, Tools,
assembled by the harness). Change the Input there, never here; check a recorded one with
`uv run --script scripts/input.py check <input.json>`. The dev-console draws it from that file.

## Explain

1. Listen to the whole explanation; do not interrupt and do not start the work.
2. Record the task as it came: what it is, the explanation, who explained it and to whom (`task.explained`).
3. Repeat it all back in your own words, the way you understood it (`understanding.taught_back`).
4. Start only when whoever explained confirms the repetition matches. A message that moves the work forward
   ("segue", "develop it") counts as the confirmation.

An agent applies this to its own requests: when someone explains a task to it, it runs `emit task.explained`
with their words verbatim (`--actor <who explained>`, `"to": <the agent>`), then `emit understanding.taught_back`
with its repetition (`--task <id>`, `--actor <the agent>`), and answers with that repetition and nothing else
before it starts.

## Design stage

- The code is `scripts/tasks.py` (`EVENTS`, the projector `_project`, `TasksJournal`). The journal is global and
  append-only, shared by every agent: `~/.local/share/tasks/events.jsonl` (override `TASKS_DIR`). Write it only
  through `uv run --script scripts/tasks.py emit <event> '<json>' [--task <id>] --actor <who>`.
- The comment above each command in `EVENTS` is the event's description for humans (the dev-console shows it).
- See it in the dev-console: add `scripts/dev_console_project.py` to `~/.local/state/dev-console/domains.txt`
  and open `/domain/tasks`. Change events in `EVENTS`, never in the console.
