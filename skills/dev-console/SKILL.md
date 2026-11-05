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
  version: 0.3.0
---

# dev-console

One file, `scripts/dev-console.py` (FastHTML + MonsterUI, PEP 723, `uv run --script`), shows
**domains**: each project file is one domain in its own context, `/domain/<slug>`; the bar lists
them and switches. It only reads. The dev-console is a domain of itself (`scripts/dev_console_project.py`,
root entity Domain, journal derived from every `dev_console_project.py` with `ast`).

## Run it

```sh
uv run --script <skill>/scripts/dev-console.py --project <skill>/scripts/dev_console_project.py \
  --project <path>/dev_console_project.py [--port 5057]   # one --project per domain
```

When the implementation is complete and verified (headless browser: load, screenshot), open it
for Gabriel in **Safari** on the domain he asked about: `open -a Safari http://127.0.0.1:5057/domain/<slug>`.
Run the server as a tracked background process (services tab), never in the user's tmux window;
adding a domain means restarting it with one more `--project` (the env of the running process
keeps the old list). It restarts by itself when this file or anything
in the project folder changes, and the page reloads; all UI state lives in the query string
(`tab`, `ev`, `side`, `w`, `e`), so a reload or a shared link reopens the same view.

## Hook up a project

Every domain lives in its own context at `/domain/<slug>` (a distinct URL per domain, never a
global one): each console route sits under that prefix and sets the current domain per request
(`use(slug)`, a ContextVar; `PROJECT`, `journal`, `SOURCE` read the current one). A project
never hardcodes `/do/…` or `/w/…`: it builds links with `BASE`, which the console sets.

Write `dev_console_project.py` next to the project's code. The contract is in
[references/project-contract.md](references/project-contract.md); the first project hooked up is
`skills/tensions/scripts/dev_console_project.py`, copy its shape.

## The screen, and the rules it follows

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
  our development process: Human → Domain.Designed (new) or Domain.Imported (existing), then the
  draft, widgets (created, updated) and actions (proposed, simulated, ran). Its screens
  are widgets of that domain: DomainView (on domain.designed) embeds the Domain tab (`?embed=1`).
- **Model** is the state machine (UML statechart vocabulary): **Human** is the initial
  pseudostate (ISO 9241-210, human-centred design), each edge is a command, each node an event.
  It is drawn from the project's `EVENTS` registry read live with `ast` (no language server):
  never hand-write a node or an edge in the console.
- **Filled node** = the journal has at least one event of that type; **outline** = none yet.
- **Click a node** = a contextual sidebar with its own tabs: Widgets (the list, each with
  `abrir`, which opens the widget in a centred popup), Código (the signatures, the event's
  command highlighted) and JSON. No global code toggle: detail belongs to the thing clicked.
- **Code on screen = signatures only**, from the real file, live, with real line numbers;
  the entity's properties are the keys of the projector's dict literal; commands are
  imperative and point to the past-tense event they record.
- **Every event has at least Observability** (count here and in the journal, a time strip,
  who). A project adds more per event in `WIDGETS`; several per event is normal.
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
- **The popup has REAL | SIMULADO** (`?mode=sim`). Widgets get `ctx.mode`; actions get
  `mode` and `step`. In SIMULADO every button works and plays the experience step by step
  (htmx `load delay` to the next `step`), ending with the expected output as the result and
  the events that would be written; nothing is sent or written. Prototype an action here
  first, and verify buttons in SIMULADO: a REAL click sends work to an agent.

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
- Taste: greys, one colour per category path, weight and space for hierarchy; enough room to
  read labels (screenshot at the user's width before saying done).

## Evolve it while using it

- Change the console in `scripts/dev-console.py` only (one file, forever). A project-specific
  view goes in the project's `WIDGETS`, not here.
- What the user corrects about the console becomes a line in this SKILL.md (a rule) or in a
  reference (depth), via `skill-smith`; screenshots go to the conversation, not the repo.
- Verify a change with the real page: load it, act (click, keys), screenshot, and read the
  DOM state when a screenshot cannot show it (`window.__cy` is the graph).

## Pitfalls

- Start it from a stable folder (`cd ~`) with absolute paths: the hot reload spawns a new
  process that reads the current folder, and a folder that changed under it kills the console.

Depth (numbers, layout, graph, server): [references/console-ui.md](references/console-ui.md).

- Keep Cytoscape node `width` numeric and edges `straight`: `width: 'label'` with bezier edges
  hid nodes and edges.
- Guard `cy.resize()` by the real box size: resizing on every ResizeObserver tick flickers.
- Keep the SSE stream and the live-reload socket from blocking a restart: the server shuts
  down with a 1 s grace.
- Fetch widget HTML with the `HX-Request: true` header and insert it with `inject()`:
  without the header FastHTML wraps the fragment in a full page whose head breaks the
  console's CSS, and plain `innerHTML` neither runs a widget's `<script>` nor wires its
  `hx-*` buttons (`inject` re-creates scripts and calls `htmx.process`).
- A project-file constant the console reads (`HOME`, `ACTIONS`, `EXPECTED_WIDGETS`) must have
  exactly that name; check `D.home` / the route after adding one, a typo fails silently.
- Keep `.sesskey` out of git: FastHTML writes its session secret next to the script it runs.
- Edit the console with small patcher scripts that assert each replacement: sed misses JS
  with quotes and backslashes without saying so.
- The user iterates fast on the look: one change, screenshot at his width (~1000 px, dark
  mode), short report; spacing moves by small steps (too tight and too loose both get
  rejected).
- The tabs other than Model and Eventos still read Tension-shaped events (proposals, linked
  items); a project without them sees them empty. Moving them into the project file is next.
