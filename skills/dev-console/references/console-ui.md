# The console UI, rule by rule

Depth for `scripts/dev-console.py`. The always-on rules are in SKILL.md; this is the
why and the numbers, read when changing a part of the screen.

## Working on the file

- Start it once in the background (services tab) and just save: `run_process`
  (watchfiles) restarts it on any change in the console folder or the project folder,
  and FastHTML `live=True` reloads the page. Kill only a stale server holding the port
  (`kill $(lsof -ti tcp:5057)`).
- Edit by small `uv run --script` patcher files that `str.replace` exact snippets and
  print one assert per replacement; sed silently misses JS with quotes/backslashes.
- FastHTML writes a `.sesskey` (session secret) next to the script it runs and in the
  project folder: keep `.sesskey` in `.gitignore` and never stage it.
- `--project` must be read before the module body runs (the app is built at import);
  the console sets `DEV_CONSOLE_PROJECT` from `sys.argv` first, then argparse.
- The SSE stream never ends: serve with `timeout_graceful_shutdown=1` or a restart
  hangs. FastHTML's live-reload socket logs `WebSocketDisconnected` on every reload;
  harmless.

## Shape

- One full-screen screen, mono `text-xs`. Tab bar first: `dev-console` · tabs ·
  `domain <every NAME as a link, the current one bold> · <journal file>` on the right.
  The entity's title lives in the rail, not in a header.
- Tabs as `<a role=tab>` with `whitespace-nowrap shrink-0` in a scrollbar-less strip
  (`<button>` gets MonsterUI focus rings and wraps). Measure `#tabs` `scrollWidth` vs
  `clientWidth` at 1440 px and ~1000 px (the user's preview width): when it clips, the
  bar must compress (letter-only tabs), never hide tabs.
- Goto keys: `g`, then the tab's letter (underlined, in `title`), a `g…` hint while
  pending, 1.2 s timeout, ignored in inputs and with modifiers. No number keys.
- `Domain` (first, default) and `Model` hide the rail and inspector; both are drawn by
  `drawGraph` (`GRAPH(tab)`): one graph function, one style.
- `INITIAL` (project file, optional): the events the Human may start with. The first is the
  root; each other one sits beside it, near the Human, and leads to the root's next step.
- `?embed=1` hides the tab bar: a widget that shows a console screen embeds it in an iframe
  (`DomainView` = the Domain tab), never a copy of its markup.
  `?embed=graph` = the graph alone (`StateGraph`): no bar, a click opens no sidebar.

## Domains and URLs

- Many `--project` flags, one domain each; slug = `SLUG` or the skill folder name.
  `/` redirects to the first domain; `/domain/<slug>` picks its open entity;
  routes: `/domain/<slug>/{t,w,do,source/stream}/…`. The JS prefixes every fetch with
  `D.base`; rail links keep `location.search` so the tab survives a switch.
- The watcher watches the console folder and every project folder.
- A self-describing domain (the dev-console's own) derives its journal from code with
  `ast` only (never import another project file to read it: imports run its side effects).

## State in the URL

`?tab=&ev=&side=&w=&e=` via `history.replaceState`; restore on load in order: tab,
sidebar (`ev`), its tab (`side`), the widget popup (`w`). Switching tab or closing the
sidebar clears `ev/side/w/e`, so a reload never reopens stale state.

## Sidebar and widgets

- Click a node: a ~420 px sidebar with name, command, count here and widget names, and
  its own tabs `Widgets` · `Código` · `JSON`. Close: ✕, `Esc`, click on the graph
  background; `Esc` closes the popup first.
- `Widgets` is a list (name, docstring first line, `abrir`); `abrir` opens the widget
  in a centred popup (`fixed inset-0`, ~860 px, 82 vh) over the console.
- Widgets render a **real** event: `?e=<id>` or the first event of that type in the
  journal; its entity is the one rendered. The list header says `dados reais: <id> ·
  <time> · <entity>`; with none, the widget says so.
- `Código`: live signatures with the event's command row highlighted; scroll only the
  sidebar (`body.scrollTop = row.offsetTop - h/2`). `scrollIntoView` scrolls `#main` too
  and pushes the graph out of view.

## Model graph (Cytoscape)

- Derived live from `EVENTS` (`ast.literal_eval` of the assignment): `lifecycle`,
  `commands`, `root` (first category's first event), `next` (root opens every other
  category's first event; inside a category each event follows the previous one).
  When a category's commands are independent, that chain is a guess: the registry
  must say each command's source state; do not fake it in the view.
- Human = initial pseudostate, a filled dot just below the root (the free downward
  direction), single edge = the root command.
- Rays: each category at its own angle; length ~185 px per step + ~80 px × |cos|;
  siblings spread by a gap scaled by |sin|. Node font 16, root 19, edge labels 15.
  Change spacing by ~20–30 % per step and screenshot.
- Labels on two lines (`Entity` / `Event`); explicit numeric node width (longest line ×
  ~10 + padding) and `curve-style: 'straight'` (`width: 'label'` + bezier hid nodes
  and edges). Edge labels in the path colour on a background box, `autorotate`; dim
  edges with `line-opacity`, never `opacity` (it fades the label too).
- Filled = the journal has an event of that type; outline = none; legend says so. No
  counts on labels.
- Load Cytoscape as a classic `<script src>` before the module. Expose the instance as
  `window.__cy` for checks; `emit('tap')` from a test must return a primitive (the
  CDP bridge chokes on the Cytoscape object).
- Fit through a ResizeObserver guarded by `WxH`; check with a MutationObserver on
  `#cy` for 2 s (0 mutations = no flicker).

## Data

Embed `{base, name, journal_types, events, state, model, entities, home}` as
`<script type="application/json">` with `</` escaped; escape every journal string
before `innerHTML`.
