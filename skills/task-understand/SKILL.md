---
name: task-understand
description: >-
  Gate before any build or write request. When the user asks you to create, write, build, implement or change
  something, do not start: first repeat back what you understood (teach-back) and wait for the confirmation.
  Questions and one-line commands skip the gate.
metadata:
  version: 0.13.3
---

# task-understand

One command runs the whole workflow, from `task.explained` to `pull_request.merged`, including adjustments, feedback and styles, the independent verification and the delivery. The domain is
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
| `task.verified` | `verify` | a fresh context (IV&V) checked the delivery against the confirmed request |
| `task.delivered` | `deliver` | the verified work was handed over: a PR, a direct change, or nothing to hand over |
| `pull_request.merged` / `pull_request.review_requested` | `merge` / `request-review` | the Human's decision on a delivered PR |

The practice is **teach-back** (health literacy: "explain it back in your own words"); the loop it closes is
**closed-loop communication** (aviation, crew resource management). Use these names; do not invent others.

Routing evals for the description (run after any change to it): [references/evals.md](references/evals.md).

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

## Models

The registry lives in `MODELS` of `scripts/tasks.py` (id → pi's `provider/model`, plan, env recipe, one-line name):
`sonnet` = `claude-bridge/claude-sonnet-5-5` (the **mukutu** Claude subscription, through the pi skill's
claude-bridge, account chosen by `CLAUDE_CONFIG_DIR=~/.claude-mukutu`), `glm` = `zai/glm-5.3` and
`glm-flash` = `zai/glm-5.3-flash` (our **GLM Coding Plan**; the key is read from `~/glm_token` into the child
process's `ZAI_API_KEY` only — never printed, logged or committed). Flat plans only: per-token providers
(OpenRouter, `~anthropic/...`) are refused, in config as in `--models`. Override and extend in
`~/.config/tasks/config.json` (`"models"` and `"default_model"`); the old `"execute"` command override is gone —
pi is the only executor. `scripts/tasks.sh models` prints the registry and, per model, whether pi
sees it right now (`pi --list-models` with the model's env; cheap, no model call).

To read results per model: every run records its own `task.executed`, so the journal accumulates, task by task,
which model ran it, how long it took, what it cost in turns and tokens, and what it answered — over time that
shows which kinds of task each model does well and with what quality.

## Explain

1. Listen to the whole explanation; do not interrupt and do not start the work.
2. Record the task as it came: what it is, the explanation, who explained it, to whom and the domain it is about
   (`task.explained`, `domain` = the dev-console slug), so it shows in that domain's Task Results tab. The domain is
   the one the work changes, never `tasks` by default: only work on this skill itself is `tasks`; a task about a
   client's board or a personal tool goes under its own slug (or none when it has no domain yet), or it pollutes
   another domain's Task Results.
3. Repeat it all back in your own words, the way you understood it (`understanding.taught_back`), and ask for the
   confirmation with the harness's ask tool whenever it has one (Hermes `clarify`, Claude Code `AskUserQuestion`,
   pi's question tool): the repetition is the question and the choices are, in this order:
   1. **Implementar <método recomendado>**: confirm and execute at once with the method the context calls for,
      named in the label. A small change whose context is already in this session (a draft in the graph, a design
      edit, a few lines) is done **by hand, here** (`Implementar aqui, à mão`): delegating it costs more than doing it.
      Long or separable work, **inside a Hermes session**, goes to the harness's own subagents (`delegate_task`,
      `Implementar com subagente`): the owner wants it kept in the session he is watching, with the agent only
      splitting, checking and merging. Elsewhere, or when he names pi, it goes to pi with the best model for it
      (step 9, e.g. `Implementar com pi · Claude Sonnet (mukutu)`; the registry's default `sonnet` when nothing
      speaks for another one). Either way each delegated task gets its own worktrunk worktree (step 13).
   2. **Pi · <recomendado> + <teste>, em paralelo**: only when the work is delegated: the recommended model plus one
      test model you pick (e.g. `Pi · Claude Sonnet + GLM 5.3, em paralelo`), each in its own worktree (step 9), to
      learn what this kind of task looks like on that model. Leave it out when option 1 is by hand.
   3. **Só confirmar**: record `understanding.confirmed` and wait for a word to execute.
   4. **Não ficou bom**: feedback (step 7).
   The repetition does not only mirror: it ends with a **Sugestão** block, what you would do better than what was
   asked (a simpler path, a missing case, a name from the literature), grounded in the context; none when nothing
   better stands out. The teach-back text in the ask is never a run-on paragraph: short blocks or a numbered list, then a blank line,
   and the question alone on the last line ("Bate?"). The tool's own free-text row is an adjustment (step 5). The
   three options of step 7 are asked the same way, one choice per style. Plain text only where the harness has no
   ask tool.
4. Start only when whoever explained confirms the repetition matches. A message that moves the work forward
   ("segue", "develop it") counts as the confirmation.
5. A reply that is not a confirmation is an adjustment: record it as a learning (`learning.recorded`, a value
   event, their words verbatim), repeat back again, and wait for the confirmation. A reply with no words in it (a
   stray `\`, an empty row) is neither: record nothing, re-ask in one line with the repetition in two bullets and the
   words that move it ("segue", "paralelo"), because a noise learning would be reused on later tasks.
6. Before repeating back, look for the learnings that apply and use them: `scripts/tasks.sh 
   use-learnings --task <id>` records `learning.used` (a value event) with the learnings recorded on this task, or on
   another that shares two or more words with it, and prints them; apply what it prints. Nothing applies, nothing is
   recorded. Give the repetition in the current default style: `scripts/tasks.sh  styles`, and
   pass `"style": "<name>"` in `understanding.taught_back`.
7. If the reply says the repetition was not good (feedback, not an adjustment of the task): `scripts/tasks.sh
    feedback --task <id> --text "<their words>"` records `feedback.given`, downscores (-1) the style
   of that repetition (`style.scored`) and prints the three styles with their guides. Write one repetition in each
   style and record them with `... options --task <id> '{"direto": "...", "passo-a-passo": "...", "exemplo": "..."}'`
   (`option.generated` x3). Show the three to the Human, each with its style name.
8. The Human picks one: `... choose --task <id> --option <option id>` records `option.chosen` (that text becomes
   the repetition to confirm) and scores (+1) its style. Wait for the confirmation as in step 4.
9. Once the Human confirms (`understanding.confirmed`), execute: `scripts/tasks.sh  execute --task <id>
   [--models sonnet,glm] [--cwd <repo>]` runs **pi** on each chosen model, in parallel, each in its own git worktree
   (`<repo>/../<repo>.task-<id8>-<model>`, branch `task/<id8>-<model>`, from the repo's HEAD), and records one
   `task.executed` per model: the run's answer, model, provider, plan, harness, exit code, duration, worktree, branch
   and what pi's JSON reports (turns, tokens, cost). No `--models` runs the registry's default. After the runs,
   review each worktree's diff and open the PR from the one that came out best.
10. Verify before delivering, with eyes that did not do the work (independent verification, IV&V): `scripts/tasks.sh
     verify --task <id> [--model sonnet] [--executed <event id>] [--cwd <dir>]`, only after a
    `task.executed`. It runs pi in a **fresh context** (`--no-session`, a flat-plan model from the registry, from the
    delivery's worktree) whose prompt holds only the task's `text`, the last confirmed teach-back and the delivery under
    test (worktree, branch, pull request and the executor's report): never the executor's transcript or its learnings.
    The verifier checks the gap, not everything: what the report says it could not check, and what only shows outside
    it (an installed app, a page); it does not re-run what the report proves with evidence unless it doubts it. It
    answers a last JSON block `{"passed", "checks": [{"what", "how", "evidence", "passed"}]}`; `task.verified` records
    it with the model, plan, duration and exit code. No parsable block, a failed check or a crashed verifier is
    `passed: false`. Failing sends the task back to `confirmed`: `execute` runs again (another model, or by hand), told
    which checks failed; then verify again. Pick the verifier model apart from the executor's when you can.
11. Deliver once it passed: `... deliver --task <id> --kind pr|direct|none [--url <link>] [--text "..."]` records
    `task.delivered`, refused unless the last verification passed. `pr` is one kind of delivery, not a mandatory step:
    `direct` is a change made in place (an issue created, a card moved), `none` is nothing to hand over.
12. When the delivery is a PR, ask the Human what to do with it (the harness's ask tool), the choices in this order,
    the recommended first by the weight of the work: prototype or experiment → **Fazer o merge direto**; product or
    client code → **Revisar antes do merge**; then **Deixar aberto**.
    - *Fazer o merge direto*: run `gh pr merge` yourself, then `... merge --task <id>` records `pull_request.merged`
      (it only records; the url comes from the delivery).
    - *Revisar antes do merge*: `... request-review --task <id> --text "<why>"` records
      `pull_request.review_requested` and the task goes back to `confirmed`: run `execute` again; the run is told
      the reason. After the changes, verify and deliver again.
    - *Deixar aberto*: no event; the PR stays as delivered.
13. **One task, one worktree, made and removed by worktrunk** (`wt`): `wt switch -c <task> --base origin/main --no-cd` to start, the PR from that worktree, and once the PR is merged `wt remove <task>`: it deletes the worktree and the branch only when its content is already in main (`⊂`), so it is the "safe to delete" check; never `-D` (an unmerged branch is the owner's call). `wt list` shows what is left. A task done by hand works the same way; only the design stage (a draft in the console's clone) has no worktree.

An agent applies this to its own requests: when someone explains a task to it, it runs `emit task.explained`
with their words verbatim (`--actor <who explained>`, `"to": <the agent>`), then `emit understanding.taught_back`
with its repetition (`--task <id>`, `--actor <the agent>`), and answers with that repetition and nothing else
before it starts.

- Put the emits in a small `.sh` in the scratch folder and run it: the person's verbatim words carry quotes and
  accents that break an inline JSON argument. Build each value with `jq -n --arg` and capture the `task_id` from the
  first emit's output for the rest. Every value needs a `text` key (the verbatim words or the repetition):
  `task.explained` is `{"title", "text", "to", "domain"}`, `understanding.taught_back` is `{"text", "style"}`,
  `learning.recorded` and `understanding.confirmed` are `{"text"}`; any other key name (`explanation`) is refused.
- When the task moves cards on a team's board (the Mukutu Project #11, a client's board), read the cards first
  and say in the teach-back who moves each one: the team may move its own cards, and the agent then only does
  what is left (often creating the new card).
- Write the teach-back in the person's language as short blocks or a numbered list, never one run-on
  paragraph, then a blank line and the question alone on the last line ("Bate?"); he reads it inside the ask tool,
  where a dense paragraph is unreadable. A follow-up that only adjusts (a new detail, "mais ou menos…") is a `learning.recorded` on the same task,
  applied at once, not a new task.
- **A draft is the drawing in the dev-console, not a PR.** "Rascunho" means the graph that shows: edit `EVENTS` and
  `TRANSITIONS` in the source the running console reads (the main clone, `scripts/tasks.py`), and the Domain tab
  redraws. Run `git status` there first: a dirty clone (another session's uncommitted edits) gets cleaned up before
  the draft goes in. The design stage is only design: no worktree, no PR, no merge, no tests and no delegating.
- Record `task.executed` honestly: `--actor` is whoever did the work (the agent itself when it worked by hand,
  the executor when `execute` ran it).
- "Concorda?" / "study and understand" asks for an opinion inside the teach-back: say where you agree and where not,
  with the literature's term and its source, and before proposing any name **read what the code already calls it**
  (an imported product's event catalogue and emit sites): proposing a name the code already settled otherwise, or an
  event the code rules out, costs a second round.
- When the task is to build something that may already exist ("implementa todo o desenho"), read the code before
  repeating back and split the repetition into **what is already done** and **what is missing**: he asked for the
  verification to come inside the teach-back, not after it.
- After `execute`, `verify` is the review: an independent context reads the diff and runs the proofs. What is
  left to you is only the gap, what neither the executor nor the verifier could run or prove (a build its
  permissions blocked, the app on screen, a screenshot): fix that, and do not re-run what was already proved with
  evidence; a second identical pass is waste. Then version, changelog and PR.

## Design stage

- The code is `scripts/tasks.py` (`EVENTS`, the projector `_project`, `TasksJournal`). The journal is global and
  append-only, shared by every agent: `~/.local/share/tasks/events.jsonl` (override `TASKS_DIR`). Write it only
  through `scripts/tasks.sh  emit <event> '<json>' [--task <id>] --actor <who>`.
- The comment above each command in `EVENTS` is the event's description for humans (the dev-console shows it).
- See it in the dev-console: add `scripts/dev_console_project.py` to `~/.local/state/dev-console/domains.txt`
  and open `/domain/tasks`. Change events in `EVENTS`, never in the console.
- Widgets on `task.executed` (in `scripts/dev_console_project.py`), validated one by one before a Tasks tab exists:
  - **TaskList**: only executed tasks, newest first, title and date (no status); a row opens the Tasks view.
  - **TaskExecutionResult**, for a person: first how it ran (method, harness, model, effort, cycle time from the
    confirmation to the end of the run, delivery as PR aberto / PR fechado / direto na main; a pi run adds provider,
    plan, exit code, duration, turns, tokens, cost), then the run's report as markdown, then the date; under them the
    independent verification (passed or not, each check with how and its evidence) and the delivery (kind and link).
    The Task List shows every task that has run, whatever came after.
  - **DomainDiff**: the diff of the domain's pseudo-code (the dev-console Code part) before and after the run;
    one line saying nothing changed when the run did not touch the domain.
  - **TaskExecutionLog**, for agents: when, who, harness, model and plan, worktree and branch, exit code, turns,
    tokens, cost, session id, event id.
  - **Tasks**: TaskList beside TaskExecutionResult, composed; it becomes the dev-console's second fixed tab
    (after Domain), filtered by the task's domain, once he approves the widgets.
  Widgets on fake data (`FAKE_*` + the "dados de exemplo" footer) mirror a real run of this skill until approved.
- A run records its `ExecutionResult` whole in `task.executed` (method, harness, model, effort, cycle_time_s,
  delivery, session, pull_request, commits, before_afters, journeys; the report in `text` may carry mermaid and
  images). A pi run (one `task.executed` per model) adds provider, plan, exit_code, duration_s, worktree, branch,
  turns, tokens and cost. `task.verified` records `{text, passed, checks, model, provider, plan, duration_s, exit_code,
  executed_id}`; `task.delivered` `{text, kind, url}`; `pull_request.merged` `{text, url}`. Pictures live in `~/.local/share/tasks/media/<task id 8>/` and are referenced as
  `media:<task id 8>/<file>`; the console serves them. A run that recorded only its text shows the text alone
  (no example data).
- A domain's Task Results tab shows only the tasks whose `task.explained` names that domain.
