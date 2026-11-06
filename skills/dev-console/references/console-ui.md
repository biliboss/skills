# The console UI, rule by rule

Depth for `scripts/dev-console.py`. The always-on rules are in SKILL.md; this is the
why and the numbers, read when changing a part of the screen.

## Working on the file

- Start it once in a herdr `services` tab and just save: `run_process`
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

- One full-screen screen, mono `text-xs`. No top bar: one thin status line (`#bar`, `h-7`, `border-t`) at the bottom:
  `<domain NAME>` (`#dom-open`, click = ⌘K) · `<module>` (`#mod-open`, click = ⌘P) · the money bar (`#money`, its popover
  opens upward) · a faint `⌘K domínio · ⌘P módulo` on the right. The work area (`#work`) takes the rest of the height.
  The entity's title lives in the rail, not in a header.
- One overlay (`#dom`), two lists: ⌘K the domains only, ⌘P `D.modules` (`{name, href}`: Domain, `TABS` with `href: null` shown in place, and
  Playground, which navigates). The Playground page ships the same status line and overlay (the canvas web is same-origin, `scripts/playground/`; the key handlers use the capture phase, so a focused canvas does not eat ⌘K / ⌘P). Open it with `domOpen('domain' | 'module')`. `keydown` ⌘P / Ctrl+P
  `preventDefault`s the print panel; inside the finder Ctrl+P is "up".
- Goto keys: `g`, then the module's letter (shown in the ⌘P overlay), a `g…` hint in the status line while
  pending, 1.2 s timeout, ignored in inputs and with modifiers. No number keys.
- `Domain` (first, default) and `Model` hide the rail and inspector; both are drawn by
  `drawGraph` (`GRAPH(tab)`): one graph function, one style.
- `INITIAL` (project file, optional): the events the Human may start with. The first is the
  root; each other one sits beside it, near the Human, and leads to the root's next step.
- `?embed=1` hides the status line: a widget that shows a console screen embeds it in an iframe
  (`DomainView` = the Domain tab), never a copy of its markup.
  `?embed=graph` = the graph alone (`StateGraph`): no bar, a click opens no sidebar.
  `?embed=side&ev=<event>` = the right menu alone (`RightMenu`): the event's sidebar, full width.
  `?embed=code&ev=<event>&side=Code` = the Code tab alone (`Code`).
  `?embed=toolbar` = the real status line alone (`Toolbar`); `&sim_tab=<name>` names an example module in SIMULADO.
  Every embed is laid out by CSS on `html[data-embed=…]`, set before `show()`.
- `HUB` (project file, optional): every start leads to it and it opens every other category.
  `TABS` (project file, optional): the modules after the fixed Domain one; the ⌘P overlay and the goto keys
  list only those.

## Domains and URLs

- Many `--project` flags, one domain each; slug = `SLUG` or the skill folder name.
  `/` is the home: `/domain/<slug>?tab=<CONSOLE_HOME>` of the first domain that declares `CONSOLE_HOME` and has an
  entity (the Kanban module), else the first domain (`_first_domain()`, which the Playground's and Agents' "Domain"
  and `/api/palette` without a domain also use); `/domain/<slug>` picks its open entity;
  routes: `/domain/<slug>/{t,w,do,source/stream}/…`. The JS prefixes every fetch with
  `D.base`; rail links keep `location.search` so the tab survives a switch.
- The watcher watches the console folder and every project folder.
- A self-describing domain (the dev-console's own) derives its journal from code with
  `ast` only (never import another project file to read it: imports run its side effects).

## State in the URL

`?tab=&ev=&side=&w=&e=&ent=` via `history.replaceState`; restore on load in order: tab,
sidebar (`ev`), the widget popup (`w`); in a widget module, the entity's sidebar (`ent`) once the widget is in. Switching
tab or closing the sidebar clears `ev/side/w/e/ent`, so a reload never reopens stale state.

Read-only JSON for agents (`scripts/console.sh` wraps them): `GET /api/domains` (`slug, name, path, origin`),
`GET /api/domains/<slug>/actions` (names in `PROJECT.ACTIONS`) and `GET /domain/<slug>/state.json?task=<entity id>`
(what the page embeds as `<script id="data">`, same builder, `money` left out). A view's URL is
`/domain/<slug>[/t/<entity id>]?tab=&ev=&side=&w=&e=`; without `/t/…` the server redirects to the entity it opens.

## Sidebar and widgets

- Click a node: a ~420 px sidebar with name, command, count here and widget names, and
  expandable parts `Widgets` (only with widgets) · `Code` · `JSON` · `Observability`, all open at first; each
  node remembers the parts the user closed in localStorage (`dev-console:part:<base>:<event>:<part>`). Close: ✕, `Esc`, click on the graph
  background; `Esc` closes the popup first.
- A widget module (`MODULE_WIDGETS`) is `#module-view` (`data-w-host`: the widget's leading `h2` hides) beside the same
  `SIDE_HTML` aside. A click, Enter or Space on a `[data-entity]` element calls `openEntity(id)`: header from
  `data-entity-name` / `data-entity-sub`, parts from `D.entity_parts` (each `GET <base>/w/<id>/<root event>/<widget>?task=<id>`,
  wrapped in `data-w-host`), then JSON (`state.json?task=<id>`, its `events`); closed parts are remembered per part for
  every entity (`dev-console:part:<base>:entity:<part>`). The selection is one `<style id="ent-sel">` rule, so it survives
  the widget's own redraws (an htmx `outerHTML` swap). A click on the module's background closes the sidebar.
- `Widgets` is a list (name, docstring first line, `abrir`); `abrir` opens the widget
  in a centred popup (`fixed inset-0`, ~860 px, 82 vh) over the console.
- Widgets render a **real** event: `?e=<id>` or the first event of that type in the
  journal; its entity is the one rendered. The list header says `dados reais: <id> ·
  <time> · <entity>`; with none, the widget says so.
- `Code`: pseudo-code of the clicked event's context, read live from EVENTS and the projector (command with its EVENTS
  line, `from`/`then`, the entity's properties and commands, this command highlighted); `?embed=code` shows it alone; scroll only the
  sidebar (`body.scrollTop = row.offsetTop - h/2`). `scrollIntoView` scrolls `#main` too
  and pushes the graph out of view.

## Model graph (Cytoscape)

- Derived live from `EVENTS` (`ast.literal_eval` of the assignment): `lifecycle`,
  `commands`, `root` (first category's first event), `next` (root opens every other
  category's first event; inside a category each event follows the previous one).
  When a category's commands are independent, that chain is a guess: the registry
  must say each command's source state; do not fake it in the view.
- Human = initial pseudostate, a filled dot in the centre; one edge per `INITIAL` start.
  Positions come from fCoSE (section Layout below), never from hand-made coordinates.
  Node font 16, root 19, edge labels 15. Change spacing by ~20–30 % per step and screenshot.
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

## Layout (fCoSE)

- The graph uses fCoSE (Balci & Dogrusoz 2022; `layout-base`, `cose-base`, `cytoscape-fcose` from jsdelivr) with
  `randomize: false` from a seed (ring = steps from the Human), so a reload draws the same picture.
- Constraints: the Human is pinned at (0,0); `INITIAL` starts are aligned horizontally with it, one on each side
  (`relativePlacementConstraint`, gap 160); the `HUB` sits below the Human and its children below the hub.
- `LAYOUT = "metro"` and `"clock"` (project file) skip fCoSE: `preset` positions computed in `drawGraph`. Metro constants:
  `STEP` 170 (between stations), `TRACK` 180 (between fanned lines), `RING` (Human to first station, grows with the
  biggest fan), `LABEL_CHARS` 14 (a label wraps at PascalCase words). Routes are cytoscape `segments` edges
  (`point = S + w (T - S) + d (-dy, dx) / |T - S|`); the label pass reads `boundingBox({includeNodes: false,
  includeLabels: true})` and pushes a colliding label outward by `LABEL_PUSH`. Check in the headless browser: every
  step of a line shares one octilinear angle, and no label box meets another label, a station or a line.
- `LAYOUT = "branch"` (or `L`, or the corner button, per domain in localStorage `dev-console:layout:<base>`) is the same
  `preset` drawing as a git graph: `branchLayout()` inside the METRO block of `drawGraph`. Constants: `COL` 170 (between
  columns), `SPURY` 72 (a spur's row offset), `GAP` 40 (between stage bands), `HEADER` 84. Order: a depth-first walk from the Human
  (then from what it does not reach, in lane order, following each lane's own order too) gives the back edges and a reverse
  post-order; an edge to an earlier stage counts as a back edge; the longest path over the forward edges gives the columns
  (inside a stage's band, so a stage resets to its own first column); a lane row never holds two stations in one column. A
  branch connector far below leaves at 45°, drops along its own gutter (70 px + 10 per branch from the same station, the
  farthest lane the innermost, so none cross) and enters at 45°; the others bend once. Stage bands are `stagehdr` nodes
  (`events: no`, excluded from the label collision pass); the label pass tries below, then above, with the same push. A
  redraw (`toggleLayout`, a source change) destroys the previous cytoscape instance and disconnects its resize observer.
- Rejected: the hand-made radial (`pos`), dagre left to right (the Human is not in the centre) and breadthfirst
  `circle` (overlaps). Forces that read well: `idealEdgeLength` 130, `nodeRepulsion` 45000, `gravity` 0.4.

## Agents module (`/agents`)

- Routes (read-only): `GET /agents` (page); `GET /agents/api/prompts?limit=&session=&kinds=prompt,cross,...&side=1`;
  `GET /agents/api/log?limit=&session=&side=1`; `GET /agents/api/entry?id=` (the whole text of one entry, capped at
  50 000 characters; 404 for an unknown id); `GET /agents/events` (SSE). The two list routes answer
  `{entries, last, sessions, mode}`; `mode` is `watch` or `poll`. Every route of the console answers 400 to a `Host` outside
  `127.0.0.1` / `localhost` / `DEV_CONSOLE_ALLOWED_HOSTS` (`TrustedHostMiddleware`, DNS rebinding); there is no CORS.
- Entry: `{id, t (ISO), session (short id; ag:xxxxxx for a sub-agent file), project (cwd folder name), kind
  (prompt|cross|notification|other|assistant|tool), text (first 600 chars), more, side, queued}`. `kind` is `prompt` for
  `origin.kind == "human"` with `promptSource` `typed` or `queued` (`queued: true`: typed while the agent was busy; the row shows a
  `queued` badge); a human without `promptSource` is `other`.
  Origins (user lines and `queued_command` attachments alike; the attachment is `{"type":"attachment","attachment":{"type":
  "queued_command","commandMode":"prompt","origin":{"kind":...},"prompt":<text or blocks>}}`, only `commandMode == "prompt"`):

  | origin.kind | user line | queued_command attachment |
  |---|---|---|
  | `human` | `prompt` if `promptSource` is `typed` or `queued` (`queued: true` for the latter), else `other` | `prompt`, `queued: true` |
  | `peer` | `cross` | `cross` |
  | `task-notification` | `notification` | `notification` |
  | anything else / none | `other` | `other` |

  The hub drops a later entry equal to an earlier one (same session, same kind, same first 200 characters, whitespace
  normalized, within 120 s; `DEDUPE_WINDOW`, `DEDUPE_CHARS`); the earliest is kept. Lines above 1 MB are skipped unparsed, and
  texts are capped like any entry. `id` is `<file-key>:<byte offset of
  the line>`; the file key is a hash of the realpath (no path leaves the server).
- SSE contract: each client has an `asyncio.Queue` fed by the watcher thread (`call_soon_threadsafe`), subscribed atomically with
  its backlog and unsubscribed when the generator ends; a 15 s timeout on `queue.get()` only emits the keep-alive. `retry: 3000`, then per entry `id: <entry id>` + `data: <entry json>`; `event: reset` (data `{session}`) when
  a file shrank (its entries are dropped, the page reloads its lists); `: keep-alive` every ~15 s. Resume with the
  `Last-Event-ID` header (what EventSource sends on reconnect) or `?after=<id>`; an unknown id resumes from now.
- Following: watchfiles (`debounce=50`, `step=20`, recursive, one watcher for every client) says which file changed; the hub
  reads from the stored offset to the end, keeps a last line without `\n` for the next read, resets a file that
  shrank, drops one that disappeared. Safety net: rescan + check all every ~5 s. Fallback: if the import fails, poll ~1 s,
  `mode = "poll"` and the page shows one warning line. Backfill: the tail of the newest files (up to `BACKFILL_FILES`, default
  150, env `DEV_CONSOLE_AGENTS_BACKFILL_FILES`), windows from the end, until about 200 prompts and 500 log entries; prompts
  in older files are not shown. The watcher is a daemon thread stopped by `Hub.shutdown` (server shutdown, atexit).
- The page: the console's status line and ⌘K / ⌘P (the Playground's script preamble plus `SWITCHER_JS`); UI state in the
  query (`view`, `session`, `show`, `pause`); row text through `textContent`, never `innerHTML`; no `<button>` (MonsterUI restyles it), spans with `role=button`.
