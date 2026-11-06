# The project contract

A project is shown by the dev-console through one Python file, `dev_console_project.py`, that the
console imports (`--project <path>`). The console's environment has FastHTML, so widgets may import it.

| Name | What it is |
|---|---|
| `NAME` | the project's name on the bar |
| `SLUG` | optional: the domain's URL, `/domain/<slug>` (default: the skill folder name) |
| `BASE` | set by the console (`/domain/<slug>`): build every link to the console with it (`f"{BASE}/do/..."`) |
| `SOURCE` | path of the file that holds `EVENTS` (read live with `ast`) |
| `EVENTS` in `SOURCE` | `{category: {command: event}}`, ordered; the comment of each command (above it or at the end of its line) is the event's description for humans, the right menu's first part: the first category's first command creates the entity; inside a category each event follows the previous one |
| `ENTITY`, `ENTITY_PLURAL` | what one item of the rail is, singular and plural |
| `ENTITIES` | `{category: entity name}`, for node labels (`Tension.Created`, `Action.Proposed`) |
| `ENTITY_KEY` | the journal field that names the entity (`tension_id`) |
| `PROJECTOR` | the function in `SOURCE` that folds events into the entity; the keys of its dict literal are the properties shown |
| `journal` | object with `read(query)`: `{}` all entities, `{"id": x}` one, `{"id": x, "history": True}` its events, `{"event": e}` events of a type, `{"history": True}` every event |
| `title_of(history, state)` | the entity's title |
| `INITIAL` | optional `["cat.event", ...]`: the events the Human may start with (Domain.Designed or Domain.Imported) |
| `MEDIA` | optional: a folder of files the domain keeps (pictures of a run), served at `/domain/<slug>/media?f=<path>` |
| `TABS` | optional: the tabs after the fixed ones, in order. Fixed: Domain, then Task Results (when the tasks domain is in the console: the tasks executed for this domain, from the tasks domain's Tasks widget; a task names its domain in `task.explained`'s `domain`) |
| `LAYOUT` | optional; **absent = `"metro"`, the default for every domain** (the order is `EVENTS`, a line follows `TRANSITIONS`, a fork is a 45° branch, a back edge is dashed). Opt out with `"clock"` or `"force"` (the old fCoSE). `"clock"`: the graph is a clock read from the code. The Human sits in the centre, the first category of `EVENTS` at 12 o'clock and the others clockwise, each category's events running outward in the order they are written. The order lives only in `EVENTS` (never a list in the project file nor a number in the console), so the drawing cannot drift from the code. `"metro"`: the same clock order drawn as a Tokyo Metro map, deterministic (preset positions, no force layout), octilinear (Nöllenburg & Wolff 2011): each category is a line in its own colour that leaves the Human along its clock hour snapped to the nearest of the 8 directions (categories that snap to the same one are fanned, parallel, one track apart); its events are stations, evenly spaced, in `EVENTS` order. Edges between neighbouring stations are the line itself (thick, no label, no arrow; a faint rail carries the line where the model has no edge); edges that leave a line (`TRANSITIONS`) are thin, grey, dashed, with at most one bend and their command label. Labels sit on a fixed side of the line, horizontal, and are pushed apart when they collide. The Human stays the biggest node and the centre |
| `TRANSITIONS` | optional `{"cat.event": ["cat.event", ...]}`: the edges, when the process branches or loops (UML statechart transitions); replaces the derived chain; a target may be a dict `{"cat.event": "command"}` to name the command of each edge when one event has several commands |
| `HUB` | optional `"cat.event"`: every start leads to it and it opens every other category (Domain.Updated) |
| `DOMAIN_DRAFT` | optional path of the domain draft (default `<SOURCE stem>_draft.py`) |
| `COST_CENTER` | optional: the id of the cost center this domain's time is billed to (a center of the Costs journal); it turns on the money bar (see the skill's Money bar); without it the journal's `domains` lists decide |
| `HOME` | optional `("category.event", "WidgetName")`: the widget the Visão tab opens with |
| `ACTIONS` | optional `{name: fn(event, dry=False)}`: the only write path, `POST /do/<event_id>/<name>` |
| `EXPECTED_WIDGETS` | optional `{name: fn(data)}`: dummy views a proposal's `expected` may name |
| `WIDGETS` | `{"category.event": [fn, ...]}`; `fn(ctx) -> component` |

`ctx` (an `EventContext`): `event`, `focus` (the real event rendered), `entity_id`, `events` (that
entity's events of this type), `state` (the projected entity), `journal_events` (this type in the
whole journal), `entities` (every entity, with `title`), `history` (every event of the entity).

**Widgets compose.** `ctx.of("category.event")` is the same entity seen through another event, so
one widget embeds another: TensionDetail renders `observation_list(ctx.of("observation.recorded"))`.
Build big widgets from small ones; never copy a small widget's markup into a big one.

**A screen is drawn from the code's value objects.** Designing a widget means touching the value object it shows,
in the domain's SOURCE: a frozen dataclass (fields typed, enums for closed sets, never raw strings), and the
design's example data is an instance of it (`FAKE_X = ExecutionResult(...)`), not a loose dict. That keeps the
screen and its documentation tied to the code, the dev-console's main goal. `VALUES = {"cat.event": "ClassName"}`
in SOURCE says which value object an event carries; the Code part lists every value object and enum of the domain.

A widget may name its visible parts, `fn.parts = [child, ...]`: the right menu's widget list shows them as a nested
tree under it (and not again at the top). Name only the parts worth seeing; the others stay composed and unlisted.

A widget with `fn.fake = True` is a design on fake data (or an embedded console screen): the console renders it
before the journal has its event.

Every widget starts with a title for humans (a heading naming what it shows), so it reads on its own in the popup
or composed inside a bigger one.

A widget's function name is its name on screen (`tension_list` → TensionList) and the first line
of its docstring is its description in the sidebar.
