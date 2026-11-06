---
name: dev-console
description: >-
  Use when opening or evolving the dev-console for a project. One full-screen read-only web console (a single FastHTML
  file) for any event-sourced project in development; the state machine of its commands and
  events drawn from the code, the entities, the journal, and widgets per event. Use when the
  user says "dev-console", "abre o console", "mostra o projeto no console", "cria um widget
  para esse evento", "liga esse projeto no dev-console", "quero ver os eventos". Not tensions
  (that skill records Tension events; this one only shows a project) and not design (screens
  of a product).
metadata:
  version: 0.11.0
---

# dev-console

One file, `scripts/dev-console.py` (FastHTML + MonsterUI, PEP 723, `uv run --script`), shows
**domains**: each project file is one domain in its own context, `/domain/<slug>`; the bar shows
the current one and ⌘K (or a click on it) opens the Domain Switcher, a fuzzy finder over an overlay
(fzf / command-palette style; never a list or cards of domains). It only reads. The dev-console is a domain of itself (`scripts/dev_console_project.py`,
root entity Domain, journal derived from every `dev_console_project.py` with `ast`).

## Run it

```sh
uv run --script <skill>/scripts/dev-console.py --project <skill>/scripts/dev_console_project.py \
  --project <path>/dev_console_project.py [--port 5057]   # one --project per domain
```

Verify in the headless browser (`browser_exec local=true`: load, read `window.__cy` and the DOM, screenshot)
or `curl`, then hand Gabriel the URL with `pbcopy`. Touch his Safari only when he asks (`open -a Safari <url>`):
driving or capturing it on every change was rejected ("pare de usar o Safari").
Run the server in a herdr tab `services` of the working workspace (`herdr tab create --workspace <ws>
--label services --cwd ~`, then `herdr pane send-text` the command piped to `tee ~/.local/state/dev-console.log`),
never as an agent's background process (it dies with the session) nor in the user's tmux window;
adding a domain needs no restart: append its `dev_console_project.py` path to
`~/.local/state/dev-console/domains.txt` and the console re-reads the list and watches the new folder. It restarts by itself when this file or anything
in the project folder changes, and the page reloads; all UI state lives in the query string
(`tab`, `ev`, `side`, `w`, `e`), so a reload or a shared link reopens the same view.

## Two independent instances

The screen state lives in the URL, so two windows on one server already navigate apart. What they share is the
live reload: the server runs with `live=True` and reloads **every** open page on each saved file, so when one agent
saves, the other agent's window reloads.

For two agents on the same project (Hermes on one window, Claude Code on the other), start a second instance:

```sh
<skill>/scripts/second.sh [port] [--from 5057]   # default 5058: same domains as :5057, no live reload
```

- It copies the `--project` flags of the instance on `--from` (read from its command line) and reads the same
  `domains.txt`, so both show the same domains; only the port differs. With nothing on `--from`, only this skill's
  own domain.
- `--no-live` (or `DEV_CONSOLE_LIVE=0`) is what turns the reload off. The server still restarts itself when code
  changes, so the new code is served, but the page changes only when its owner reloads it.
- One instance per agent: the first keeps 5057, the other takes 5058 and opens it in a browser tab or window
  of its own. The native window (below) is a single one, on 5057 by default.
- Run it in a terminal tab of its own like the first one, never as an agent's background process.

## A native window

`app/` is a Swift package (product `DevConsole`, bundle `com.biliboss.devconsole`): one regular Dock app with one
window holding a `WKWebView` (`isInspectable = true`) on the console page (default `http://127.0.0.1:5057/`; the
FastHTML server still serves it, nothing moved out of the web). The title follows the page title. The console's UI
is made for **two thirds of a screen**: on first launch the window takes two thirds of the main screen's visible
width and its full height, docked to the right (the left third stays free for a terminal or chat); `dock left|right`
re-docks it at two thirds, `resize` sets any size, and the frame is remembered after that.

The agent drives it only through `scripts/window.sh`, and the two files in `~/.local/state/dev-console-window/`
have one writer each:

| file | writer | content |
|---|---|---|
| `command.json` | `scripts/window.sh` only | `id` (increments), `action`, `side`, `url`, `width`, `height`, `js`, `updated_at`; the app applies each new `id` once |
| `state.json` | the app only | `url` (follows in-page `pushState` too), `title`, `visible`, `width`, `height`, `last_command_id`, `last_result` (the JS result or the error, for `eval`), `last_message`, `updated_at` |

```sh
W=<skill>/scripts/window.sh
$W open http://127.0.0.1:5057/domain/tensions   # also: reload | show | hide | resize <w> <h> | dock left|right
$W eval 'document.title'                        # the result lands in state.json last_result
$W wait                                         # blocks until last_command_id is the last sent id (5 s cap), prints state
$W status                                       # prints state.json
$W install                                      # builds app/build-app.sh, copies to ~/Applications, opens it; $W quit stops it
```

A page button talks back with `window.webkit.messageHandlers.devconsole.postMessage({...})`: the object is written to
`state.json` as `last_message`. That is the only native feature.

- **To read the DOM or take a screenshot, keep using the headless browser on the same URL**; the window is for the
  person to look at and for the agent to move (open a view, dock, hide), and `eval` is for a quick read of one value.
- **Never write either file by hand.** The id rule (above both the last one sent and the last one applied) and the
  atomic `mv` live in the script. A bad command is answered in `last_result` as `error: ...`, and its id is consumed.
- **Read the layout from the graph, not the pixels**, when a screenshot cannot be trusted (the Mac's display asleep
  or locked gives a black `screencapture`, and a headless capture can time out): `window.sh eval` a reduction of
  `window.__cy` (per category, the angle of each node from `#human`; overlap counts of rendered label boxes), then
  `wait | jq -r .last_result`. One angle per category = a metro line in the right clock direction.
- **Do not run `install` just to open a view.** It rebuilds and relaunches; use it when the app is missing or its code changed.
- `cd app && swift build && swift test` runs the `ConsoleCore` tests (command decode, apply once per id, state, frames).
  If `swift` fails on an SDK mismatch, `export SDKROOT=$(xcrun --sdk macosx --show-sdk-path)` (`build-app.sh` does it).
  `DEV_CONSOLE_WINDOW_STATE_DIR` moves both files (tests); `DEV_CONSOLE_URL` sets the app's default page.

## Playground

`/playground` (no slug) is a **mode** beside Domain, tied to no domain: the console's top bar and, filling the rest,
the design-playground's web (a tldraw canvas, `~/biliboss/dev/design-playground`) in an `iframe`. The canvas is composed,
never copied, and the console adds nothing to that project. **Its web has no canvas-only mode, so its chat shows on the
right as it is**; hiding it is a change in the design-playground, the owner's call.

- `DEV_CONSOLE_PLAYGROUND_URL` (default `http://127.0.0.1:5317`) is the web. When it does not answer the page says so in
  one line with the command that starts it (`scripts/motor.sh http --servidor`, skill `design`), looks again every 3 s
  through `GET /playground/up` and opens the canvas as soon as it answers; never a broken frame.
- **The money bar**: no domain, so `PLAYGROUND_COST_CENTER` (env `DEV_CONSOLE_PLAYGROUND_COST_CENTER`, default
  `biliboss-skills`) names the cost center; the same bar and the same records (`domain: playground`), through
  `/domain/playground/time*` (the money routes answer for the Playground; a real domain called `playground` wins).
- **Modules.** Every page carries `D.modules` (`{name, href}`: Domain, Playground); the Domain Switcher (⌘K, the
  same script on both pages: `SWITCHER_JS` is cut out of the main page's JS, one copy) lists each module except Domain as
  a fixed last row, after the domains, shown when it matches the query. The ⌘P module switcher that comes next reads `D.modules`.
- Test it like any change (second console on another port, empty registry, temp `COSTS_DIR`), pointing the env at a
  closed port for the "not running" line and at a design-playground started on another port (`PORT=5318 ABRIR_WEB=0
  DADOS_DIR=<temp> bun run src/main.ts --servidor`) for the canvas; never at the owner's 5317. Keep the registry
  in a folder of its own: the watcher restarts the console on any write beside it (the money clock writes `running.json`).

## Hook up a project

Every domain lives in its own context at `/domain/<slug>` (a distinct URL per domain, never a
global one): each console route sits under that prefix and sets the current domain per request
(`use(slug)`, a ContextVar; `PROJECT`, `journal`, `SOURCE` read the current one). A project
never hardcodes `/do/…` or `/w/…`: it builds links with `BASE`, which the console sets.

Write `dev_console_project.py` next to the project's code. The contract is in
[references/project-contract.md](references/project-contract.md); the first project hooked up is
`skills/tensions/scripts/dev_console_project.py`, copy its shape.

## The screen, and the rules it follows

- **Follow the template; never invent a screen.** Any new tab, graph or panel reuses what the
  console has: `TABS` + `KEYS`, `drawGraph` (fCoSE, Human pinned in the centre, filled/outlined nodes),
  the contextual sidebar (expandable parts: Widgets, Code, JSON, Observability), the popup with REAL | SIMULADO, state in the
  query. A Mermaid diagram or a second Cytoscape function with its own layout was rejected twice.
- **Tabs are the first element**; each has a vim-style goto (`g` then the underlined letter:
  `g d` Domain, `g m` Model). Colours for unknown categories come from a fixed palette by
  category order, so any domain draws. Esc closes the popup, then the sidebar.
- **Domain is the first tab and the default** (`g d`); it reuses the Model view (`drawGraph`, the
  same sidebar and popup). One graph, one style: a new graph tab joins `GRAPH(tab)`, never a second
  Cytoscape function or its own layout.
- **The domain draft**: when `<SOURCE stem>_draft.py` (or `DOMAIN_DRAFT`) is missing, the console
  writes it once from EVENTS and the projector: dummy classes (DDD bases AggregateRoot, Entity,
  ValueObject, DomainEvent), fields typed `Any`, command stubs `-> CategoryEvent: ...`, no
  implementation. It never overwrites it: the draft is the user's to edit.
- **The dev-console is built with the dev-console.** Its own domain (`scripts/console_domain.py`) is
  our development process: Human → Domain.Designed (new) or Domain.Imported (existing) → Domain.Updated (the hub), which links
  Event.Updated, Widget.Updated and Tab.Updated (one event each for create, change, delete). Its
  journal is `scripts/console_domain.jsonl`, seeded from the code once and then edited by hand. When Gabriel names a
  "view"/"screen"/"menu" of this domain he means **the console's own screen**, embedded as a
  widget, not a new design: DomainView (the Domain tab, `?embed=1`), StateGraph (graph alone,
  `?embed=graph`), RightMenu (the event sidebar alone, `?embed=side&ev=…`), each an `Iframe` with
  `fn.fake = True`, plus Code (`?embed=code`), Toolbar (`?embed=toolbar`, the real tab bar) and
  WidgetList. A domain's widgets hang on **Domain.Updated only**: the starts (Designed,
  Imported) have none. An embed never shows the tab bar (except Toolbar, which is the bar).
- **Design events small** (rules in skill `design-taste`, Domain design): one `Updated` per element
  for create, change and delete; every start leads to one hub (`HUB`); a configuration value (the
  home widget) rides in an event's value, never as its own event; keep out of the domain what
  belongs to a widget (Action was cut). Fix a prototype fact by editing the JSONL, not with code.
- **Composable, always.** A widget that shows something the console already draws composes that
  component: WidgetList calls `render_widget_list(slug, event)` (the right menu's own list, set on
  every project module by the console), screens embed with `?embed=`. A second copy of a view is a bug.
  A piece of the toolbar that belongs to a domain (the money bar) is also that domain's widget (CostToolbar on
  `time_entry.started`): an `Iframe` of `?embed=money`, an embed mode that shows only that piece of the bar.
- **Playground is a mode, not a tab.** Free sketching with the agent (screens, dashboards, comparisons) lives in a
  dev-console mode beside Domain, not tied to any domain: the agent operates a canvas (the design-playground's,
  composed without its own chat, since the Hermes chat sits beside the window) and a sketch is promoted to a domain
  widget or a real component only when he says so. Proposing it as a per-domain "Esboço" tab was the misread.
- **Tabs per domain.** Domain is the one fixed tab; a project lists the rest in `TABS` (absent =
  Domain only). Tension-shaped tabs live only in the tensions project's `TABS`.
- **A list row opens on click, Enter or Space** (tabindex 0, aria-label, the button stays), with the
  same gray look: never `role="button"` on a row, Pico paints it as a blue centred button.
- **Model** is the state machine (UML statechart vocabulary): **Human** is the initial
  pseudostate (ISO 9241-210, human-centred design), each edge is a command, each node an event.
  It is drawn from the project's `EVENTS` registry read live with `ast` (no language server):
  never hand-write a node or an edge in the console.
- **Filled node** = the journal has at least one event of that type; **outline** = none yet.
- **Click a node** = a contextual sidebar of expandable parts (all open at first, closed ones remembered per
  node in localStorage), in this order: Description (for humans), Widgets (only when the event has widgets; each
  row opens the widget in a centred popup), Code, JSON, Observability. No global code toggle: detail belongs to
  the thing clicked.
- **Description comes only from the code comment** of the command in `EVENTS` (the comment lines above it, or
  the one at the end of its line), written in Portuguese for a human. Never a separate dict in the project file:
  the code is the single source, so write the sentence there.
- **Code = short pseudo-code of the event's context**, read live from EVENTS and the projector: the command
  with its real EVENTS line, `from`/`then`, the entity's properties (keys of the projector's dict literal) and
  its commands, this one highlighted. Commands are imperative and point to the past-tense event they record.
- **Every event has Observability, as the right menu's last part** (count here and in the journal, a time
  strip, who), never as a row of the widget list. The Widgets part shows only when the event has a widget
  of its own (Domain.Designed and Domain.Imported have none: Code, JSON, Observability).
- **A widget shows only what the model has.** Design it from the event's real value (an
  Observation is a sentence, where, when, who; it has no state, no group, no "resolved"):
  never add fields, groupings or summaries the model does not record. Write the text for a
  human (a sentence about the world, not "DVM-231 está em Doing"). Clarity over detail: say the
  fact plainly and keep times, sources and IDs out of the sentence.
- **Human widgets vs agent widgets.** A widget for a person shows the sentence and the
  timestamp only (no source, no actor, no ids) and reads only records written for humans
  (`audience: human`); everything else goes to a separate `…Log` widget or the JSON tab.
  Pair them per event (ObservationList + ObservationLog).
- **Widgets compose.** A bigger widget embeds smaller ones through `ctx.of("category.event")`
  (TensionDetail renders ObservationList); never copy a small widget's markup into a big one.
  Contract: [references/project-contract.md](references/project-contract.md).
- **Widgets render real data**: the first event of that type in the journal, or `?e=<id>`.
  With none, the widget says so. The one exception is the design step below.
- **What to do comes first.** A detail widget (TensionDetail) shows the gap, then the
  proposals up front (ProposalList, always open), and the observations folded below
  (`<details>`, open state in the query). Observations are context, not the headline.
- **Visão opens the project's `HOME` widget** (the detail widget); a project without `HOME`
  keeps the generic summary. Ask which screen when "add this component" is ambiguous
  (`clarify`, three choices) instead of guessing.
- **A proposal row** = title and subtitle for humans, one CTA ("Executar no Bili local",
  a project `ACTIONS` entry) and an **"Esperado no final"** block under it: what the work
  will deliver, as a stock `report` (markdown), `list`, `table`, or a cheap dummy widget the
  proposal brings (`EXPECTED_WIDGETS`), always marked "exemplo". Proposing with a dummy
  widget is the preferred way to show intent before anything is built.
- **The popup has REAL | SIMULADO** (`?mode=sim`), except for a widget whose root has `data-real-only`
  (generated from a SKILL.md or code): the toggle hides and `mode` is cleared. Widgets get `ctx.mode`; actions get
  `mode` and `step`. In SIMULADO every button works and plays the experience step by step
  (htmx `load delay` to the next `step`), ending with the expected output as the result and
  the events that would be written; nothing is sent or written. Prototype an action here
  first, and verify buttons in SIMULADO: a REAL click sends work to an agent.

## Design a new domain from a story

When Gabriel tells a story ("meu sócio fazia isso com os estagiários") and wants to see it as a domain:

1. Write it in `/tmp/<name>/` (`<name>.py` with EVENTS, the projector and a JSONL journal class; `dev_console_project.py`;
   `<name>.jsonl` with one example walk), then append the project path to the domain registry: no restart.
   **A domain of the house's own work** (costs, tasks, anything about how he works, not a client's product) skips
   `/tmp` and `~/biliboss/dev`: it is a skill of biliboss/skills from the first draft (step 6 at once), or he asks
   for the move.
   **Design comes before implementation**: when he says "design first" / "faz o design no Domain", stop any
   executor already implementing that feature and draw the domain; the implementation follows the approved drawing.
2. **Name events after the story's own actors and verbs** (Task.Explained → Understanding.TaughtBack), not
   generic document nouns (Brief.Created → Narrative.Generated read as unrelated to the story and were rejected).
   An event says the intent, not a CRUD change: List.ItemAdded / ItemRemoved (Segment's e-commerce spec: "Product
   Added to Wishlist"), not List.Updated for a save; keep `Updated` for the thing itself changing (a rename). The
   event starts with the entity of its line (List.ItemAdded, not Item.Saved inside the list line).
   Look up the literature's term for the practice (teach-back, closed-loop communication) and cite it in the
   module docstring. **The entity noun must be universal** (home, school, any company): Task, not Demand
   ("demand" reads as an imposition in English and is Brazilian work slang).
3. **Start with the fewest events the story needs** (often two); he cuts extra steps (request, clarify, confirm)
   himself. Branches and loops go in `TRANSITIONS` only when he asks for them.
4. Each command gets its Portuguese comment (the Description), on **its own line** in the category's dict: two
   commands written on one line (`{"start": "started", "stop": "stopped"}`) share the comment above them, so both
   events show the same description. The example journal mirrors the story with real-sounding content.
   **Ship the first widgets with the domain**, on the example journal's real data: one per event worth seeing for a
   person (a list of the entities, the day's summary as `HOME`), each starting with its title. A drawn domain with no
   widgets gets asked "e os widgets, foram feitos?". Then give him the URL.
5. When he asks about a word (etymology, origin), discuss without editing anything.
6. **When he says it will be a skill**, move it out of `/tmp` into `skills/<name>/` of biliboss/skills:
   `scripts/<name>.py` + `dev_console_project.py`, a short SKILL.md marked "Design stage"
   (entity, the events table, the literature's term), CHANGELOG 0.1.0, `.gitignore` (`.sesskey`, `__pycache__/`),
   the path in `.claude-plugin/plugin.json` and a README line; swap the `/tmp` line in the domain registry for
   the new path. Leave the `/tmp` folder (deleting is his call). Ship as one PR.
   **Its events go to a global append-only JSONL**, like tensions: `~/.local/share/<name>/events.jsonl` (override
   `<NAME>_DIR`), written only by `scripts/<name>.py emit <event> '<json>' [--<entity> <id>] --actor <who>`;
   no example journal inside the repo. **Name the skill `<entity>-<action>`** (task-understand): one command
   runs the whole workflow, never one skill per command, and it does not collide with harness built-ins
   (`/tasks` is Claude Code's). The domain keeps its plural set name (Tasks: `SLUG` tasks, the journal folder)
   and its console `NAME` says where it lives ("Biliboss Skills - Tasks").
7. **Then use the skill right away** on his next request (dogfood): record his words verbatim through `emit`,
   reply with the skill's output (for tasks: the teach-back), and continue only after he confirms.
8. **"Deixa visível", "tipo o draft", "não é para implementar" = draw only.** Add the new events to `EVENTS`
   (each with its Portuguese comment, marked "rascunho: só no grafo") and the edges to `TRANSITIONS`; touch no
   projector, emit or widget. The outlined nodes show what is not built yet. Implementing it unasked was the
   misread.
9. **Edges are commands.** When one event is recorded by two commands (score / downscore → Style.Scored), list both
   in `EVENTS` and name each edge's command in `TRANSITIONS` with a dict target (`{"style.scored": "downscore"}`);
   one label `score | downscore` on both edges was rejected. An act of the person (confirm) is an edge from the
   Human: put that event in `INITIAL`, not after the agent's event.

## Import a domain from existing code

For a product whose code already records domain events (Domain.Imported):

1. Read a **detached worktree of `origin/main`** (`git worktree add --detach <dir> origin/main`), never another
   session's checkout, and never edit the product repo: the project file lives outside it (`~/biliboss/dev/<name>/`).
   This is long work: give it to a subagent with the console contract and the read-only rule.
2. `EVENTS` follows the code's own kinds, each line traceable (`# kind: ListingShared`), with the Portuguese comment
   taken from the code's docs; the journal returns one placeholder entity when production's journal is unreachable.
   **Start from the product's event catalogue and its emit call sites**, not from memory: the registry where each kind
   is declared with its sentence and product question (Via: `visitor("Kind", stage, desc, question)` in
   `events/core.ts`) and a grep of the emit calls (`fact(`, `appendTo(`) for where each one is born (file:line).
   Keep apart **entity streams** (`list:<id>`: ListCreated, ListItemSaved; the entity's own facts) and **analytics
   facts** on another stream (the visitor's ItemSaved, ListOpened): mixing them into one line misdraws the domain.
   Before proposing a new event name, check whether the code already has one; a code comment like "nothing is
   updated" vetoes a proposed `Updated`. A renamed kind stays a draft here; the rename in the product is a card for
   whoever owns that repo.
   A code-graph tool (graphify: `uv tool install graphifyy`, then `graphify update . --no-cluster` and
   `graphify cluster-only . --no-label`, code-only and no LLM; `GRAPHIFY_QUERY_LOG_DISABLE=1`) parses symbols with
   tree-sitter, so it does not see event kinds written as strings: use it for impact (`affected`, `path`) and
   navigation, with an ignore list for `.claude`, `.data`, `vault`, `archive` (about half the nodes otherwise).
3. Every domain is drawn as a metro map by default (no `LAYOUT` needed; he asked for it as the console's standard,
   not one project's); a big import drawn at once is "bom mas complexo" without it (see
   the contract; `"clock"` still works for the plain clock), keep only the first hand in `EVENTS`
   (the north at 12 o'clock is the access to the system by a Human with no role yet; then where the Human takes a
   role) and park the other categories, as imported, in `EVENTS_BACKLOG` in the same file until he orders the next
   hand. The clock order is the order of `EVENTS`: never a list in the project file nor a number in the console.
   The map's order is the order of `EVENTS`: the first category leaves the Human at 12 o'clock, the others follow
   clockwise, each category is a line and its events are the stations in the order written.
4. **A metro line follows `TRANSITIONS`, not adjacency in `EVENTS`**: a station's parent is its earliest in-line
   predecessor by a forward edge; where it forks, the longest path stays the trunk and the others leave as 45°
   branches; a backward edge (reactivation) stays a dashed cross edge. When reviewing an imported category, ask
   "sequence or fork?": usually only activation is a sequence (sign up → verify), then the active entity forks into
   repeatable acts (edit, change slug, come back), and silence loops back to a session.
   **The categories spread evenly around the Human, like sun rays** (`round(8 * i / N)`): he preferred it over one
   clock hour per category or one direction each. Ask before changing the spread rule.
   **For a big imported domain he leans to a linear reading, like `git log --graph`**: the Human at the top left,
   one horizontal lane per category in `EVENTS` order, a lane branching off the event that leads into it, edges into
   another lane as dashed merges, and columns by funnel stage (AARRR: acquisition, onboarding, aha, usage, retention)
   taken from the product's catalogue as `STAGES`. Rays stay for small domains (Tasks, Costs); offer a key to toggle
   both so he compares on the real domain. When he asks "sugira algo" about layout, sketch it in ASCII first.
5. The Human is the biggest node (twice an event node's size on the clock), the graph opens centred on it, and "◎ Centralizar Human" brings it back.
   The native window hot-reloads like the browser when the project file changes.
6. **The branch layout** (`LAYOUT = "branch"`, or `L` on any domain): the same domain as a git graph (`git log --graph`) read
   left to right. The Human is the root at the top left; each category of `EVENTS` is a horizontal lane (a branch), top to
   bottom in `EVENTS` order; a line follows `TRANSITIONS` as the metro does, but its fork is a 45° spur inside the lane. A lane is
   born where its transition comes from (its first station sits one column right of the station that leads into it, joined
   by a 45° connector); a lane nothing leads into hangs from the Human on a grey spine; any other edge into a lane is a
   merge (thin, grey, dashed, with its command). **Columns are funnel stages** when the project declares them: `STAGES =
   {"cat.event": "stage"}`, `STAGE_ORDER = [...]` (and `STAGE_LABELS = {stage: text}` for the header); a stage is a band of
   columns with a faint header at the top, and an edge that would go back to an earlier stage is drawn as a loop (dashed),
   never as a line running left. Without `STAGES` a column is the longest step count from the Human. `L` (focus not in an
   input) or the small `ramos` / `raios` button in the graph's top-right corner toggles branch and metro on any domain, kept per
   domain in localStorage. It opens with the Human at the top left and the zoom fitting the height (a 20-lane import is tiny
   until zoomed: scroll or zoom right to read on). Check in the headless browser (`window.__cy`, `cy.scratch('branch')` has the lanes'
   y bands and the stages' x bands): every lane's stations inside one y band, no station left of an earlier stage's band, no two
   rendered label boxes overlapping, the toggle switching and persisting after a reload. Serve the check from a folder the
   console does not watch for screenshots (it watches the registry's folder and the project folders: a file written there reloads it).

## Design a widget with the user

1. **Settle the look before the connection.** When Gabriel says "define o widget" or "ignora a
   conexão", edit the widget function in the project's `WIDGETS` directly, with fake data in a
   module constant next to it (`FAKE_<NAME>`) and a dim footer "dados de exemplo: o desenho
   vem antes da conexão". Never a separate HTML mock or a `::preview`: he wants it **in his
   open console**; hot reload plus the query state (`?ev=…&w=…`) puts it on his screen as you save.
2. **Fake data mirrors the entity's real records**, rewritten for a human: same count, same
   facts, same sources and times; only the wording changes. Do not invent states, groups,
   summaries, "new since your visit" marks or "superseded" lines the model does not record —
   the first design that did was rejected.
3. **Set the tone with one choice, not a guess.** When the human copy reads weak, rewrite the
   first item three ways and ask with `clarify` (one question, three choices); apply the chosen
   tone to every other item and record it as a rule here. His standing pick: clarity over
   precision (no times or counts inside the sentence).
4. **Connect after he approves**: keep the approved markup, swap the constant for `ctx`
   fields, delete the constant and the footer. Keep the old real-data version as
   `<name>_real` only until the swap.
- **A domain that is a skill gets a Skill widget** ("<Entity> Skill", e.g. Task Skill) on the event the skill
  acts on, generated only from the real skill, never from fake data: name and description from the SKILL.md
  frontmatter, the numbered steps from its own section (`## Explain`), and the **Input as a Cytoscape graph read
  with `ast` from `scripts/input.py`** (the contract: frozen dataclass value objects plus `check`). A value object
  that holds others is a compound node; one marked `assembled_by_harness` (Session Context) is dashed and dim.
  Lay it out with `preset` columns (inputs left, Input, then the event), since it is a flow, not a state machine.
  The SKILL.md points to `input.py` instead of listing the Input again. Its root carries `data-real-only`, so the
  popup hides REAL | SIMULADO (nothing to simulate in a widget generated from a real source).
- **Widgets before the view that holds them.** When he asks for a new tab or view with widgets, build the widgets
  first on their event (each opens in the popup), let him validate them, and only then add the tab: building the
  tab first skips the validation he wants. "It's prototype time" = fake data (step 1), even when real data exists.
- **Every widget starts with a title** for humans (`H2`, what it shows: "Tarefas executadas", "Resultado da
  execução"), so it reads alone in the popup and composed inside a bigger one.
- **A list filtered to one state does not repeat that state** on each row (a list of executed tasks shows title
  and date only).
- **A detail widget that does not land gets replaced, not patched**: when he names the thing it should represent
  ("o Task Execution Result, na verdade"), build that widget and swap it into the composing view.
- **Code has a sibling, the Diff**: when work changes a domain, show the change as a diff of the same pseudo-code
  the Code part draws (lines kept in grey, removed struck through, added marked; the only colours in it).
- Taste: greys, one colour per category path, weight and space for hierarchy; enough room to
  read labels (screenshot at the user's width before saying done).

## Evolve it while using it

- Change the console in `scripts/dev-console.py` only (one file, forever). A project-specific
  view goes in the project's `WIDGETS`, not here.
- What the user corrects about the console becomes a line in this SKILL.md (a rule) or in a
  reference (depth), via `skill-smith`; screenshots go to the conversation, not the repo.
- Verify a change with the real page: load it, act (click, keys), screenshot, and read the
  DOM state when a screenshot cannot show it (`window.__cy` is the graph), in the headless browser.
  Then copy the exact view's URL (`?ev=…&w=…`) with `pbcopy`; he opens it himself.
- Gabriel steers in short messages while you work: apply each one at once, verify, and ship each
  settled change as its own small PR. Start every PR branch from `origin/main` (`git stash push --
  skills/dev-console; git checkout -B <branch> origin/main; git stash pop`): after a squash merge an
  old branch conflicts, and `gh-app` refuses force push (a PR already CONFLICTING: commit, then `git checkout -B
  <branch>-2 origin/main && git cherry-pick <sha>`, push, close the old PR, open the new one). Stage only `skills/dev-console` (and the
  project files you touched); other sessions leave changes in the same repo.
  **One task, one worktree, made and removed by worktrunk** (`wt`): `wt switch -c <task> --base origin/main --no-cd` to start, the PR from that worktree, and once the PR is merged `wt remove <task>`: it deletes the worktree and the branch only when its content is already in main (`⊂`), so it is the "safe to delete" check; never `-D` (an unmerged branch is the owner's call). `wt list` shows what is left.
  Before `git pull` on the clone the console reads (`~/src/skills`), commit what the background review left there
  (skill lessons, version bumps) as its own small PR: a pull over them aborts, and a stash pop conflicts on the
  `version:` line (resolve to one version above both).

## Money bar

Everything is monetary, so every domain belongs to a cost center (see `cost-track`); a domain with one shows the money
bar in its toolbar. Nothing is stored by the console: the Costs journal is the only storage and cost-track's
`scripts/costs.py` (found at `../../cost-track/scripts/costs.py`; missing means no bar) its only writer.

- **The bar:** the center name; what it spent today in R$, ticking every second; for a client `de R$ <budget>` with a
  thin progress line, red over budget, plus `hoje a <cliente> pagou R$ X/h`; for an investment `<nome> · R$ X hoje`,
  no budget; the rate (R$/min; a click cycles min, hora, dia, kept in localStorage); ▶ / ⏸. A click on the center name
  opens a popover with today per center and the total.
- **The center of a domain:** `COST_CENTER = "<id>"` in its project file, else the center whose `domains` lists the
  slug in the journal (`costs.center_of`). The Costs domain declares `biliboss-skills`; Tasks and dev-console are in
  that center's `domains`. A project that lives outside (Via Corretor) is listed in the journal, never declared here.
- **The record:** `POST /domain/<slug>/time/start` and `/time/stop` (`ended_by`) emit `time_entry.started` and
  `time_entry.stopped` (`text`, `domain`, `seconds`, `rate_hour`, `cost`, `ended_by`); the server is the only writer
  (through `costs.py`). The rate in force is stored on each entry, so a price change never rewrites the past. The
  running stretch sits in `running.json` in the costs folder (`COSTS_DIR`), so a hot reload keeps it; the page pings
  `time/beat` every 10 s and a stretch silent for 45 s is closed (`close`). `GET /domain/<slug>/time` reads the numbers.
- **What stops the clock:** Pause, switching domain, 5 min idle on the Mac, and, in a browser tab only, the page
  hidden (`visibilitychange`). In the native app a hidden page never stops it: a window covered by the chat or hot-
  reloaded behind it reports `document.hidden` while he is still working (detect the app by
  `window.webkit.messageHandlers.devconsole`). **Never** window blur and never `document.hasFocus()`.
  When he says to leave the clock running, re-check it after every console edit and restart it if it shows ▶. In the native app, every 5 s it calls
  `window.devconsoleIdle(seconds)` with the Mac's idle time (`systemIdleSeconds()` in `ConsoleCore`: the any-input event
  type `~0`, because `.null` answers with the time since boot); a normal browser falls back to its own input idle.
  Coming back does **not** restart the clock: the button shows ▶. An embed (`?embed=`) never shows the bar, runs the
  clock or ends another domain's stretch.
- **Testing it:** a second console on another port with `COSTS_DIR=<temp copy of events.jsonl>` and
  `DEV_CONSOLE_REGISTRY=<empty file>`, never the real journal.

## Pitfalls

- Start it from a stable folder (`cd ~`) with absolute paths: the hot reload spawns a new
  process that reads the current folder, and a folder that changed under it kills the console.
- Test a change on a second console (another port, `DEV_CONSOLE_REGISTRY=<empty file>` so only your `--project`
  shows, temp env overrides for any data files) and read it in the headless browser; never point his native window at
  that port, and if you did, `window.sh open` it back to 5057 before you stop: he takes the test console for his and
  thinks a domain vanished. Kill only the test server (`pkill -f 'port <n>'` is flagged as self-termination; kill its
  process session instead).
- An imported domain whose journal is empty (the real one lives where the Mac cannot read it) must still return one
  placeholder entity from `read({})`, or the page shows "Nenhum … no diário" and draws no graph.
- Never put every event of a category in `INITIAL[1:]`: `derive` drops initial alternates from their category's chain,
  an empty chain raises `IndexError` and the page 500s. Hang a Human decision off an event in `TRANSITIONS` instead.
- Centre on the Human after `fit`, then zoom out around it until the bounding box fits: centring alone pushes the far
  nodes off screen.
- In the native window, `eval` right after `open` may run before the page draws (`window.__cy` undefined): `wait`,
  then give it a few seconds. Make the web view the window's first responder, or `document.hasFocus()` stays false.

Depth (numbers, layout, graph, server): [references/console-ui.md](references/console-ui.md).

- Keep Cytoscape node `width` numeric and edges `straight`: `width: 'label'` with bezier edges
  hid nodes and edges. The one exception is a two-way pair from `TRANSITIONS` (A→B and B→A): class `loop`,
  `bezier` with a control-point step, or the two straight edges lie on top of each other.
- Guard `cy.resize()` by the real box size: resizing on every ResizeObserver tick flickers.
- Keep the SSE stream and the live-reload socket from blocking a restart: the server shuts
  down with a 1 s grace.
- Fetch widget HTML with the `HX-Request: true` header and insert it with `inject()`:
  without the header FastHTML wraps the fragment in a full page whose head breaks the
  console's CSS, and plain `innerHTML` neither runs a widget's `<script>` nor wires its
  `hx-*` buttons (`inject` re-creates scripts and calls `htmx.process`).
- A project-file constant the console reads (`HOME`, `ACTIONS`, `EXPECTED_WIDGETS`) must have
  exactly that name; check `D.home` / the route after adding one, a typo fails silently.
- Per-event model data the sidebar reads (`coverage`, `descriptions`) lives on `M()` (the model payload),
  not on `D`: reading `D.x` silently shows the empty fallback.
- An event that belongs to no entity (`worth.updated` has no `cost_center`) must still render its widgets: read the
  entity key with `focus.get(...)` and keep the page's id, or `_ctx` raises `KeyError` and the widget 500s.
- Read an entity's optional fields with `.get` in console code (`status`, `updated_at`, `event_count`):
  a new domain's projector does not have them and the page 500s. Read the server log in the services pane
  (`~/.local/state/dev-console.log`) on any 500 before guessing.
- Keep `.sesskey` out of git: FastHTML writes its session secret next to the script it runs.
- Lay out an embed with CSS keyed on `html[data-embed=…]`, set before `show()`: `show()` re-renders
  `#main`, so JS that hides or resizes elements first is lost or hits the wrong node.
- An embedded console screen points at the domain whose event it shows (the dev-console's own
  `SLUG` for its process events): pointing at `ctx.entity_id` opened another domain without that
  event ("comando undefined").
- Edit the console with small patcher scripts that assert each replacement: sed misses JS
  with quotes and backslashes without saying so. Never add a `#` comment in the middle of a Python expression line
  (a dict entry followed by `**derive(...)`): it swallows the rest of the line. After every patch to
  `dev-console.py` run `uv run --with python-fasthtml python -m py_compile <file>`: the hot reload restarts on save,
  and a syntax error kills the console for every domain, his native window included.
- While the money clock runs in his window, do not open another domain's page anywhere (curl, `fetch`, headless):
  a page GET of another domain closes the running stretch (`domain_change`). Check other domains on a test console.
- The user iterates fast on the look: one change, screenshot at his width (~1000 px, dark
  mode), short report; spacing moves by small steps (too tight and too loose both get
  rejected).
- The Tension-shaped tabs (Proposed Actions, Observations, …) are still console code; only the
  tensions project lists them in `TABS`. Moving their markup into the project file is next.
