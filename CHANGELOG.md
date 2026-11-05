# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html). Cada skill guarda também o próprio `CHANGELOG.md`.

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
