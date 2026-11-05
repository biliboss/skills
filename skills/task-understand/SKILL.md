---
name: task-understand
description: >-
  One command, /task-understand, runs the whole workflow of the Tasks domain (design stage). A Task is explained to someone, and at the end that person repeats it back the way they
  understood it (teach-back), so the gap between what was meant and what was understood shows before the
  work starts. Use when the user says "task-understand", "teach-back", "repete do jeito que entendeu", "explica a
  tarefa", "vou te passar uma tarefa". Not tensions (gaps between actual and desired reality) and not
  the Linear (the team's board).
metadata:
  version: 0.8.0
---

# task-understand

One command runs the whole workflow, from `task.explained` to `task.executed`, including adjustments, feedback and styles. The domain is
**Tasks** (plural: the set of tasks), shown in the dev-console as Biliboss Skills - Tasks at `/domain/tasks`;
other workflows of the domain come as `task-<action>` skills.

**One Entity:** Task, a piece of work explained to someone (the most universal name: a to-do at home, an
assignment at school, a ticket in a software team).
**The core loop** (the full list, with each event's description, is `EVENTS` in `scripts/tasks.py`):

| Event | Command | What happened |
|---|---|---|
| `task.explained` | `explain` | someone explained the task, in their own way and with the time it needed |
| `understanding.taught_back` | `teach_back` | at the end, the receiver repeated it back the way they understood it |
| `understanding.confirmed` | `confirm` | the Human said the repetition matches (an edge from the Human) |
| `task.executed` | `execute` | the receiver, or the configured executor, did the work |

The practice is **teach-back** (health literacy: "explain it back in your own words"); the loop it closes is
**closed-loop communication** (aviation, crew resource management). Use these names; do not invent others.

## Styles

Three fixed styles of repetition, in `STYLES` of `scripts/tasks.py`, each with a version: `direto` (one sentence),
`passo-a-passo` (numbered steps), `exemplo` (a paragraph with a concrete example). Changing a style's guide means
bumping its version, and the style then starts again from zero. A style gains a point when its option is chosen
(`style.scored`, `score`) and loses one when its repetition gets feedback (`style.scored`, `downscore`). The default
style is the one with the highest score (a tie goes to the first declared); `tasks.py styles` shows it.

The full flow, as drawn in the graph: `task.explained` → `learning.used` → `understanding.taught_back` → the Human
confirms (`understanding.confirmed` → `task.executed`), or adjusts (`learning.recorded` → `learning.used`), or gives
feedback (`feedback.given` → `style.scored` downscore + `option.generated` x3 → `option.chosen` → `style.scored` score).

## Input

What reaches the agent when someone explains a task is a value object, and its contract is
`scripts/input.py`: User Prompt, Skill and Session Context (System Prompt, History, Memory, Environment, Tools,
assembled by the harness). Change the Input there, never here; check a recorded one with
`uv run --script scripts/input.py check <input.json>`. The dev-console draws it from that file.

## Explain

1. Listen to the whole explanation; do not interrupt and do not start the work.
2. Record the task as it came: what it is, the explanation, who explained it, to whom and the domain it is about
   (`task.explained`, `domain` = the dev-console slug), so it shows in that domain's Task Results tab.
3. Repeat it all back in your own words, the way you understood it (`understanding.taught_back`), and ask for the
   confirmation with the harness's ask tool whenever it has one (Hermes `clarify`, Claude Code `AskUserQuestion`,
   pi's question tool): the repetition is the question and the choices are **Bate, pode seguir** (confirm),
   **Não ficou bom** (feedback, step 7) and the tool's own free-text row for an adjustment (step 5). The three options
   of step 7 are asked the same way, one choice per style. Plain text only where the harness has no ask tool.
4. Start only when whoever explained confirms the repetition matches. A message that moves the work forward
   ("segue", "develop it") counts as the confirmation.
5. A reply that is not a confirmation is an adjustment: record it as a learning (`learning.recorded`, a value
   event, their words verbatim), repeat back again, and wait for the confirmation.
6. Before repeating back, look for the learnings that apply and use them: `uv run --script scripts/tasks.py
   use-learnings --task <id>` records `learning.used` (a value event) with the learnings recorded on this task, or on
   another that shares two or more words with it, and prints them; apply what it prints. Nothing applies, nothing is
   recorded. Give the repetition in the current default style: `uv run --script scripts/tasks.py styles`, and
   pass `"style": "<name>"` in `understanding.taught_back`.
7. If the reply says the repetition was not good (feedback, not an adjustment of the task): `uv run --script
   scripts/tasks.py feedback --task <id> --text "<their words>"` records `feedback.given`, downscores (-1) the style
   of that repetition (`style.scored`) and prints the three styles with their guides. Write one repetition in each
   style and record them with `... options --task <id> '{"direto": "...", "passo-a-passo": "...", "exemplo": "..."}'`
   (`option.generated` x3). Show the three to the Human, each with its style name.
8. The Human picks one: `... choose --task <id> --option <option id>` records `option.chosen` (that text becomes
   the repetition to confirm) and scores (+1) its style. Wait for the confirmation as in step 4.
9. Once the Human confirms (`understanding.confirmed`), execute: `uv run --script scripts/tasks.py execute --task <id>
   [--cwd <folder>]` runs the configured executor and records `task.executed` with its answer. The default executor is
   the claude-code skill's print mode on the mukutu account with Sonnet, by that skill's rules: `--max-turns 30`, only
   the tools the work needs (read, edit, `uv run`, git status/diff), its own git worktree (`--worktree task-<id>`, so
   edits never land on a shared checkout) and JSON output (cost, turns and session id go into `task.executed`).
   Change it in `~/.config/tasks/config.json` as `{"execute": {"command": [..., "{prompt}"], "env": {}}}`; `{task}` is
   the task id's first 8 characters. After it runs, review the worktree's diff and open the PR from it.

An agent applies this to its own requests: when someone explains a task to it, it runs `emit task.explained`
with their words verbatim (`--actor <who explained>`, `"to": <the agent>`), then `emit understanding.taught_back`
with its repetition (`--task <id>`, `--actor <the agent>`), and answers with that repetition and nothing else
before it starts.

- Put the emits in a small `.sh` in the scratch folder and run it: the person's verbatim words carry quotes and
  accents that break an inline JSON argument. Capture the `task_id` from the first emit's output for the rest.
- Keep the teach-back to one short paragraph in the person's language, ending with one question ("Bate?");
  a follow-up that only adjusts (a new detail, "mais ou menos…") is a `learning.recorded` on the same task,
  applied at once, not a new task.
- Record `task.executed` honestly: `--actor` is whoever did the work (the agent itself when it worked by hand,
  the executor when `execute` ran it).
- When the task is to build something that may already exist ("implementa todo o desenho"), read the code before
  repeating back and split the repetition into **what is already done** and **what is missing**: he asked for the
  verification to come inside the teach-back, not after it.
- After `execute`, review the executor's work before shipping: read its diff, run its tests yourself (it may have
  been denied the commands to run them) and fix what its report says it could not check; then version, changelog
  and PR.

## Design stage

- The code is `scripts/tasks.py` (`EVENTS`, the projector `_project`, `TasksJournal`). The journal is global and
  append-only, shared by every agent: `~/.local/share/tasks/events.jsonl` (override `TASKS_DIR`). Write it only
  through `uv run --script scripts/tasks.py emit <event> '<json>' [--task <id>] --actor <who>`.
- The comment above each command in `EVENTS` is the event's description for humans (the dev-console shows it).
- See it in the dev-console: add `scripts/dev_console_project.py` to `~/.local/state/dev-console/domains.txt`
  and open `/domain/tasks`. Change events in `EVENTS`, never in the console.
- Widgets on `task.executed` (in `scripts/dev_console_project.py`), validated one by one before a Tasks tab exists:
  - **TaskList**: only executed tasks, newest first, title and date (no status); a row opens the Tasks view.
  - **TaskExecutionResult**, for a person: first how it ran (method, harness, model, effort, cycle time from the
    confirmation to the end of the run, delivery as PR aberto / PR fechado / direto na main), then the run's report
    as markdown, then the date.
  - **DomainDiff**: the diff of the domain's pseudo-code (the dev-console Code part) before and after the run;
    one line saying nothing changed when the run did not touch the domain.
  - **TaskExecutionLog**, for agents: when, who, executor, exit code, turns, cost, session id, event id.
  - **Tasks**: TaskList beside TaskExecutionResult, composed; it becomes the dev-console's second fixed tab
    (after Domain), filtered by the task's domain, once he approves the widgets.
  Widgets on fake data (`FAKE_*` + the "dados de exemplo" footer) mirror a real run of this skill until approved.
