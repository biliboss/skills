# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html). Cada skill guarda também o próprio `CHANGELOG.md`.

## [0.27.0] - 2026-11-06

### Added

- `retro` 0.1.1, `cost-track` 0.3.1, `task-understand` 0.13.3: `scripts/retro.sh`, `costs.sh` and `tasks.sh` as the entry point of each CLI (the uv Python script stays the implementation).

### Changed

- `skill-smith` 0.3.1: Step 3 says the `.sh` is the interface every harness calls.

## [0.26.0] - 2026-11-06

### Added

- `retro` 0.1.0: the `/retro` skill, an after-action review of the session that turns the owner's corrections into rules for the right skills (he picks, one PR applies); `retro.py` CLI with `emit`, `lessons`, `rejected-rules` and `scan`.

## [0.25.0] - 2026-11-06

### Added

- `dev-console` 0.11.0: ⌘P switches the module (Domain, the project's tabs, Playground) on every page, ⌘K lists domains only; a bottom status line (domain · module · money) replaces the tab bar, on a domain page and on the Playground too; the native app owns ⌘P and ⌘K in a menu so no print panel opens.

### Fixed

- `dev-console`: loading `/playground` no longer ends a running stretch (only the first trusted gesture posts `enter`); `?embed=money` shows the bar.
- `task-understand` 0.13.2 (patch): the Task Results tab no longer 500s on a journal with `method: "pi"`.

## [0.24.0] - 2026-11-06

### Added

- `dev-console` 0.10.0: the Playground mode (`/playground`), the design-playground's canvas composed in an iframe beside
  Domain and tied to no domain, with its own cost center on the money bar and a fixed last row in ⌘K.

## [0.23.0] - 2026-11-06

### Added

- `dev-console` 0.9.0: `LAYOUT = "branch"`, the graph as a git graph read left to right (the Human at the top left, each
  category a lane, a lane born where its transition comes from, a merge as a dashed edge); funnel-stage columns from
  `STAGES` / `STAGE_ORDER` / `STAGE_LABELS`; `L` and a corner button toggle branch and metro on any domain.

## [0.22.0] - 2026-11-05

### Added

- `dev-console` 0.7.0: `LAYOUT = "metro"`, the graph of a big domain drawn as a Tokyo Metro map (octilinear lines from
  the clock, stations in `EVENTS` order, labels that never overlap); a big domain uses it, the order lives only in `EVENTS`.

## [0.21.0] - 2026-11-05

### Added

- `dev-console` 0.6.0: the money bar in the toolbar of every domain with a cost center (spent today ticking, the day
  budget for a client, the rate, ▶ / ⏸, a popover with today per center); the clock writes Costs events.
- `cost-track` 0.3.0: `scripts/costs.py` is the only writer of the Costs journal (`emit` CLI plus the module API the
  console imports); tests in `scripts/test_costs.py`.

### Removed

- `timer` (the menu bar countdown): the clock now lives in the dev-console's money bar and everything lands in the
  Costs journal.

## [0.20.0] - 2026-11-05

### Added

- `cost-track` 0.1.0 (design stage): the Costs domain, everything has a cost; cost centers, worth and time
  entries, drawn in the dev-console.

## [0.19.0] - 2026-11-05

### Added

- `dev-console` 0.5.0: a native macOS window the agent drives. `DevConsole.app` shows the console page in a `WKWebView` (docked at two thirds of the screen, title follows the page); `scripts/window.sh` is the only writer of `command.json`, the app the only writer of `state.json` (url, title, size, last command and result, messages the page posts through the bridge). The headless browser stays how an agent reads the DOM.

## [0.18.0] - 2026-11-05

### Changed

- `task-understand` 0.13.0: `verify` (independent verification, IV&V, in a fresh pi context), `deliver` and the PR
  decision (`merge`, `request-review`) become real commands; a failed verification or a requested review sends the
  task back to execution; the dev-console shows the verification and the delivery under the run.

## [0.16.0] - 2026-11-05

### Added

- `timer` 0.1.0: a countdown in the Mac menu bar driven by the agent through `scripts/timer.sh`; the StatusTimer app only displays the state file.
- `timer` 0.2.0: the menu bar looks like the macOS clock (Nerd Font timer icon, monospaced menu bar font, label only in the tooltip).

## [0.17.0] - 2026-11-05

### Changed

- `task-understand` 0.11.0: pi é o executor, só nos planos flat — a assinatura Claude da mukutu (claude-bridge) e
  o GLM Coding Plan (zai; a chave lida de `~/glm_token` só no env do filho). A mesma tarefa pode rodar em paralelo
  em vários modelos, cada um no seu worktree (`task/<id8>-<model>`), com um `task.executed` por modelo (model,
  provider, plano, exit code, duração, turnos, tokens, custo); OpenRouter e provedores por token são recusados.
  O pedido de confirmação passa a ser: implementar com o modelo recomendado, recomendado + um modelo de teste em
  paralelo, só confirmar, não ficou bom — e o teach-back na pergunta é blocos curtos ou lista numerada, com a
  pergunta ("Bate?") sozinha na última linha.

## [0.15.0] - 2026-11-05

### Changed

- `dev-console`, laid out for two thirds of a MacBook screen (1140 × 1000): right menu at a third of the window,
  the graph header in one line (reading key behind "?"), "N widgets" as the sidebar subtitle, each start's own
  events kept on its side of the Human; Task Results opens on the domain's newest task.

### Added

- `dev-console`: `/domain/<slug>/media?f=<path>` serves the files a domain keeps (`MEDIA`), never outside it.
- `task-understand` 0.10.0: the real ExecutionResult with mermaid and pictures; Task Results filtered by domain.

## [0.14.0] - 2026-11-05

### Changed

- `task-understand` 0.9.0: the confirmation asks Confirm and implement (with the method), Just confirm, or Not good.

## [0.13.0] - 2026-11-05

### Fixed

- `dev-console`: the Task Results tab takes the whole width (no entity rail, no JSON inspector); tab labels keep their
  spaces; report lists have one marker at the body's size; the result names the selected task.

### Changed

- `task-understand` 0.8.0: the teach-back asks for the confirmation with the harness's ask tool.

## [0.12.0] - 2026-11-05

### Added

- `dev-console`: Task Results, the second fixed tab of every domain (when the tasks domain is loaded): the tasks
  executed for that domain, composed from the tasks domain's widget.
- `task-understand` 0.7.0: a task names its domain.

## [0.11.0] - 2026-11-05

### Added

- `task-understand` 0.6.0: typed value objects for the execution and the Task.Executed widgets.
- `dev-console`: the Code part lists the domain's value objects and enums in subsections (the entity and the event's
  value object open, other value objects then types closed; each remembered in localStorage); the widget list is a
  nested tree (`fn.parts`); widgets that come from real sources hide REAL | SIMULADO; mermaid is available to widgets;
  every widget starts with a title; screens are drawn from the code's value objects (contract).

## [0.10.0] - 2026-11-05

### Added

- `task-understand` 0.5.1: the whole process implemented (learnings used, feedback with downscore, three fixed
  versioned styles, options, choice with score, default style = highest score); the default executor follows the
  claude-code skill (max turns, allowed tools, own worktree, JSON output). Implemented by the executor itself, the
  first real run of `tasks.py execute`.

## [0.9.0] - 2026-11-05

### Added

- `task-understand` 0.4.0: configurable executor (default Claude Code on mukutu with Sonnet) and the draft of the
  feedback, learning and style process.
- `dev-console`: the right menu opens with Description (from the code comment of each command); `TRANSITIONS` may
  name the command of each edge; several commands may record one event; domains join through
  `~/.local/state/dev-console/domains.txt` with no restart.

## [0.8.0] - 2026-11-05

### Added

- `task-understand` 0.3.0 (design stage): one command runs the Tasks domain's workflow, Task.Explained then
  Understanding.TaughtBack (teach-back), with a global journal `~/.local/share/tasks/events.jsonl`, the Input
  contract in `scripts/input.py` and the Task Skill widget in the dev-console.

## [0.7.0] - 2026-11-05

### Changed

- `dev-console` 0.4.0: its own domain is Human → Domain.Designed or Domain.Imported → Domain.Updated (the hub, `HUB`), which links Event.Updated, Widget.Updated and Tab.Updated; Action left the domain. The journal is an editable JSONL (`console_domain.jsonl`).
- `dev-console`: the graph uses fCoSE with the Human pinned in the centre; the tab bar shows each domain's `TABS` (Domain fixed), with Nerd Font icons.
- `dev-console`: the right menu is expandable parts (Widgets, Code, JSON, Observability), open at first, closed ones remembered per node in localStorage; Code is a short pseudo-code of the event's context.
- `dev-console`: widgets compose the real components (WidgetList, Toolbar, Code, DomainView, StateGraph, RightMenu); a WidgetList row opens on click, Enter or Space; the Domain's widgets hang on Domain.Updated only.
- `dev-console`: the server runs in a herdr `services` tab.

## [0.6.0] - 2026-11-05

### Added

- `dev-console` 0.3.0: many domains in one console, each in its own context at `/domain/<slug>` (repeat `--project`).
- `dev-console` describes itself: its own domain is the development process (Human → Domain.Designed or Domain.Imported; widgets designed, approved, connected; actions proposed, simulated, ran), journal derived from code with `ast`; DomainView and StateGraph widgets embed the console's own Domain tab (`?embed=1`, `?embed=graph`).
- `INITIAL` (several starting events), `DOMAIN_DRAFT` (a dummy `<SOURCE>_draft.py` written once when missing) and `fn.fake` (design widgets render before their event exists) in the project contract.

### Changed

- `dev-console`: Domain is the first tab and reuses the Model graph (`drawGraph`), sidebar and popup.
- `tensions`: action links use the console's `BASE` (`/domain/<slug>`).

## [0.5.0] - 2026-11-05

### Added

- `dev-console` 0.1.0: one-file FastHTML console for any event-sourced project in development (`--project`): the state machine of commands and events drawn from the code, entities, journal, and widgets per event in a contextual sidebar and a centred popup.

### Changed

- `tensions` 0.2.0: `EVENTS` is `{category: {command: event}}` and smaller; `created_at` in the projection; the project file `dev_console_project.py` hooks it into the dev-console.

## [0.4.0] - 2026-11-04

### Added

- `tensions` 0.1.0: shared append-only JSONL journal for meaningful domain events. One Python stdlib script, one SKILL.md and optional scripts/justfile recipes, without NATS, MCP, or Python packages.
 
## [0.3.0] - 2026-11-04

### Added

- `design` 0.1.0: telas no design-playground com os widgets reais do produto. O wrapper sai do código do produto (`scripts/wrapper.sh build|conferir|pastas|foto`) e o agente vira o motor do MCP (`scripts/motor.sh claude|pi|http`). O que é de cada produto (a referência, a receita, os wrappers e os rascunhos) mora fora do repo, em `DESIGN_PRODUTOS`. Chaves novas no `casa.env.example`: `DP_DIR`, `DP_URL`, `DP_URL_REMOTA`, `DP_TOKEN`, `DESIGN_PRODUTOS` e `PRODUTO_<P>_REPO`/`_REMOTO`.

## [0.1.2] - 2026-11-03

### Changed

- `skill-smith`: as ações de um skill são scripts `.sh`, não um servidor MCP.

## [0.1.1] - 2026-11-03

### Changed

- `sync` 0.1.1: o trabalho de outra sessão também é commitado, em commit separado.

## [0.1.0] - 2026-11-03

### Added

- O plugin `biliboss-skills` e o marketplace `biliboss`, no molde do mattpocock/skills.
- `wiki-smith` (de biliboss/wiki-smith, 0.1.2), `skill-smith` (de biliboss/skill-smith), `lp-draft`, `sync` (do biliboss) e o novo `setup-biliboss`.
