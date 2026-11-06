# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.14.0] - 2026-11-06

### Changed

- Step 9 in Claude Code runs the confirmed task on a native subagent (Agent tool, Sonnet, in the background, in its
  own worktree) instead of pi: same account and tools as the session, the report comes back here. `task.executed`
  is emitted by hand with `harness: claude-code`, `exit_code` and `worktree`. pi stays the executor in harnesses
  without subagents (Hermes, pi) and for the parallel model comparison (option 2).

## [0.13.0] - 2026-11-05

### Added

- `tasks.py verify` (IV&V): pi in a fresh context (`--no-session`, a flat-plan registry model, the delivery's worktree)
  checks a `task.executed` delivery against the confirmed request. The prompt holds only the task's text, the last
  confirmed teach-back and the delivery (worktree, branch, PR, the executor's report); never the executor's transcript
  or learnings. It asks for the gap, not everything, and for a last JSON block `{passed, checks}`; `task.verified`
  records it. No parsable block, a failed check or a crashed verifier is `passed: false`.
- `tasks.py deliver --kind pr|direct|none`: `task.delivered`, refused unless the last verification passed.
- `tasks.py merge` and `tasks.py request-review --text`: `pull_request.merged` and `pull_request.review_requested`,
  only after a `task.delivered` of kind `pr`.
- The projector knows `verified`, `delivered` and `merged`; a verification that did not pass, and a review
  requested, put the task back at `confirmed` so `execute` runs again, told which checks failed or why the review
  was asked. `ExecutionResult` gains `verification` and `delivered` (defaults `None`); `outcome_of(history)` attaches
  what followed the last run; older events and `result_from` are unchanged.
- SKILL.md steps 10 to 12: verify → deliver → the PR ask (merge direct for a prototype, review first for product or
  client code, then leave it open).
- dev-console: Task Execution Result shows the verification (each check with its evidence) and the delivery (kind and
  link) under the run; the Task List shows every task that has run.

### Changed

- The four events are real: the "rascunho, só no grafo" marks are gone from `EVENTS`.

## [0.12.2] - 2026-11-05

### Changed

- The description is the routing gate that passed the evals ("Gate before any build or write request…"): 6/6 on
  Haiku, against 0/2 for the 0.12.1 one. Results in `references/evals.md`.

## [0.12.1] - 2026-11-05

### Changed

- The description leads with the trigger, "Use when a work request arrives", and says what stays out (a quick
  question, a one-line command, a timer), so it can route without a line in the profile.

### Added

- `references/evals.md`: five routing evals to run in fresh sessions (Hermes, or pi on Haiku/Sonnet), with the
  first results.

## [0.12.0] - 2026-11-05

### Added

- Draft in the graph (no commands yet): `task.verified`, a new outside context (IV&V) that checks the delivery against
  the confirmed request, back to `task.executed` when it does not pass; `task.delivered`, with the kind of delivery
  (PR, direct change, none); and the Human's decision on a PR, `pull_request.merged` or `pull_request.review_requested`.
- The repetition ends with a **Sugestão** block: what the agent would do better, grounded in the context.

### Changed

- Option 1 of the confirmation names the method the context calls for: a small change already in this session's
  context is done by hand here, and only long or separable work goes to pi; the parallel option only when delegating.

## [0.11.0] - 2026-11-05

### Changed

- The executor is **pi** (`pi -p --no-session --mode json`), never Claude Code: the same task runs in parallel on
  several models, each in its own git worktree (`<repo>.task-<id8>-<model>`, branch `task/<id8>-<model>`, from the
  repo's HEAD), and one `task.executed` is recorded per model (model, provider, plan, harness, exit code, duration,
  worktree, branch, turns, tokens, cost), so over time we learn which kinds of task each model does well.
- The confirmation choices: implement with the recommended model (the label names it), the recommended plus one
  test model in parallel, just confirm, not good; the teach-back in the ask is short blocks or a numbered list, a
  blank line, and the question ("Bate?") alone on the last line.

### Added

- `MODELS` registry in `tasks.py` (id → pi's provider/model, plan, env recipe, one-line name): `sonnet` =
  `claude-bridge/claude-sonnet-5-5` (mukutu subscription), `glm` = `zai/glm-5.3` and `glm-flash` = `zai/glm-5.3-flash`
  (GLM Coding Plan; the key is read from `~/glm_token` into the child process's `ZAI_API_KEY` only, never printed
  or logged); override and extend in `~/.config/tasks/config.json` (`"models"`, `"default_model"`).
- `tasks.py models`: the registry and, per model, whether pi sees it right now (`pi --list-models` with the model's
  env; cheap, no model call).
- `ExecutionResult` gains, with defaults, the pi-run fields (provider, plan, exit_code, duration_s, worktree,
  branch, turns, tokens, cost_usd); `result_from` parses them without breaking older events, and the Task Results
  and Task Execution Log widgets show them; `test_flow.py` covers the registry, the refusal and the parallel
  execute with a fake pi on PATH (no real model call).

### Removed

- The `{"execute": ...}` config override and the Claude Code default executor: pi on the flat plans is the only
  executor; per-token providers (OpenRouter, `~anthropic/...`) are refused.

## [0.10.0] - 2026-11-05

### Added

- `result_from`: the real ExecutionResult of a `task.executed` (pictures as `media:` paths, served by the console);
  the result widget, Before and After and Journey read it, with example data only when nothing ran.

### Fixed

- Task Results lists only the tasks of the domain on screen (the tasks domain no longer shows every task).

## [0.9.0] - 2026-11-05

### Changed

- The confirmation choices are, in order: Confirm and implement (naming the method: the default executor or the
  better one for the task), Just confirm, Not good (feedback); free text is an adjustment.

## [0.8.0] - 2026-11-05

### Changed

- The teach-back asks for the confirmation with the harness's ask tool (Hermes `clarify`, Claude Code
  `AskUserQuestion`): confirm, not good (feedback) or a free-text adjustment; the three styled options too.

## [0.7.0] - 2026-11-05

### Added

- A task names its domain (`task.explained` value `domain`); the Tasks widget, renamed Task Results, filters by it
  and is the dev-console's second fixed tab.

## [0.6.0] - 2026-11-05

### Added

- Typed value objects in `tasks.py`: `ExecutionResult` (the value of Task.Executed) with `SessionRef`, `PullRequest`,
  `Commit`, N `BeforeAfter` and N `Journey` of `Picture`s, and enums `Method`, `Harness`, `Model`, `Effort`,
  `Delivery`, `PullRequestState`; `VALUES` maps each event to its value object.
- Widgets on Task.Executed, designed on an `ExecutionResult` instance: Tasks (Task List + Task Execution Result),
  Task Execution Result (method, harness, model, effort, cycle time, delivery; the report with mermaid; Before and
  After, Journey and Domain Diff composed), Task Execution Log, Before and After, Journey, Domain Diff; media open
  fullscreen and the arrows walk through them.

## [0.5.1] - 2026-11-05

### Fixed

- The default executor follows the claude-code skill: `--max-turns 30`, allowed tools only, its own git worktree and
  JSON output (cost, turns, session id recorded in `task.executed`); before, it edited the shared checkout with no cap.
- `test_flow.py` runs with `uv run python scripts/test_flow.py`.

## [0.5.0] - 2026-11-05

### Added

- `tasks.py use-learnings` (real `learning.used`), `feedback` (`feedback.given` + downscore), `options` (`option.generated` x3),
  `choose` (`option.chosen` + score) and `styles` (scores, default = highest).
- Three fixed, versioned styles (`STYLES`); the projector keeps `options` and `style`; `scripts/test_flow.py`.
- SKILL.md: Styles section and steps 6 to 9 (learnings, feedback, options, choice).

## [0.4.0] - 2026-11-05

### Added

- `tasks.py execute --task <id>`: runs the configured executor on a confirmed task and records `task.executed`;
  default is Claude Code print mode on the mukutu account with Sonnet, configurable in `~/.config/tasks/config.json`.
- Draft of the whole process in the dev-console graph: Learning (recorded, used), Understanding.Confirmed by the
  Human, Feedback.Given, three styled Options (generated, chosen), Style.Scored by score or downscore, Task.Executed.
- Steps 5 to 7 in SKILL.md: adjustments become learnings, learnings are used before repeating back, execute after
  the confirmation.

## [0.3.0] - 2026-11-05

### Changed

- Renamed to `task-understand`: one command runs the whole workflow; `/tasks` collided with Claude Code's
  built-in command. The domain stays Tasks (`/domain/tasks`, `~/.local/share/tasks`).

## [0.2.0] - 2026-11-05

### Added

- Global append-only journal `~/.local/share/tasks/events.jsonl` (override `TASKS_DIR`), shared by every agent;
  `tasks.py emit` and `tasks.py read` on the command line.
- `scripts/input.py`: the Input contract (frozen value objects) with `check`; the Task Skill widget in the
  dev-console, generated from SKILL.md and input.py.
- The Explain steps in SKILL.md.

### Removed

- The sample journal inside the repo (`scripts/tasks.jsonl`): only real events now.

## [0.1.0] - 2026-11-05

### Added

- Domain design: Task.Explained → Understanding.TaughtBack (teach-back), a hand-editable JSONL journal and the
  dev-console project file.
