---
name: dev-console
description: >-
  Open and evolve the dev-console, one full-screen read-only web console (a single FastHTML
  file) for any event-sourced project in development; the state machine of its commands and
  events drawn from the code, the entities, the journal, and widgets per event. Use when the
  user says "dev-console", "abre o console", "mostra o projeto no console", "cria um widget
  para esse evento", "liga esse projeto no dev-console", "quero ver os eventos". Not tensions
  (that skill records Tension events; this one only shows a project) and not design (screens
  of a product).
metadata:
  version: 0.1.0
---

# dev-console

One file, `scripts/dev-console.py` (FastHTML + MonsterUI, PEP 723, `uv run --script`), shows a
**project**. The console works at the level of the Project: the bar says which one. It only reads.

## Run it

```sh
uv run --script <skill>/scripts/dev-console.py --project <path>/dev_console_project.py [--port 5057]
```

Open `http://127.0.0.1:5057` in the Hermes browser (`desktop_preview open`). Run it in the
services tab, never in the user's tmux window. It restarts by itself when this file or anything
in the project folder changes, and the page reloads; all UI state lives in the query string
(`tab`, `ev`, `side`, `w`, `e`), so a reload or a shared link reopens the same view.

## Hook up a project

Write `dev_console_project.py` next to the project's code. The contract is in
[references/project-contract.md](references/project-contract.md); the first project hooked up is
`skills/tensions/scripts/dev_console_project.py`, copy its shape.

## The screen, and the rules it follows

- **Tabs are the first element**; each has a vim-style goto (`g` then the underlined letter:
  `g m` Model). Esc closes the popup, then the sidebar.
- **Model** is the state machine (UML statechart vocabulary): **Human** is the initial
  pseudostate (ISO 9241-210, human-centred design), each edge is a command, each node an event.
  It is drawn from the project's `EVENTS` registry read live with `ast` (no language server):
  never hand-write a node or an edge in the console.
- **Filled node** = the journal has at least one event of that type; **outline** = none yet.
- **Click a node** = a contextual sidebar with its own tabs: Widgets (the list, each with
  `abrir`, which opens the widget in a centred popup), Código (the signatures, the event's
  command highlighted) and JSON.
- **Every event has at least Observability** (count here and in the journal, a time strip,
  who). A project adds more per event in `WIDGETS`; several per event is normal.
- **Widgets render real data only**: the first event of that type in the journal, or `?e=<id>`.
  With none, the widget says so; never a sample.
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

- Keep Cytoscape node `width` numeric and edges `straight`: `width: 'label'` with bezier edges
  hid nodes and edges.
- Guard `cy.resize()` by the real box size: resizing on every ResizeObserver tick flickers.
- Keep the SSE stream and the live-reload socket from blocking a restart: the server shuts
  down with a 1 s grace.
- The tabs other than Model and Eventos still read Tension-shaped events (proposals, linked
  items); a project without them sees them empty. Moving them into the project file is next.
