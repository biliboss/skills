# The project contract

A project is shown by the dev-console through one Python file, `dev_console_project.py`, that the
console imports (`--project <path>`). The console's environment has FastHTML, so widgets may import it.

| Name | What it is |
|---|---|
| `NAME` | the project's name in the status line and in ⌘K |
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
| `LAYOUT = "branch"` | opts in to the git-graph drawing (the person's `L` choice, kept per domain, wins over it). A git graph read left to right: the Human at the top left is the root; each category of `EVENTS` is a horizontal lane (a branch), top to bottom in `EVENTS` order; inside a lane a line follows `TRANSITIONS` as in metro (the longest path is the trunk, a fork drops into a 45° spur inside the lane, a back edge is a dashed arrow). A lane starts one column right of the station (in another lane) whose transition leads into it, joined by a 45° connector, like a git branch leaving main; a lane nothing leads into hangs from the Human along a grey spine; any other edge into a lane is a merge: thin, grey, dashed, octilinear, at most one bend, with its command label. Labels are horizontal, below the station (above on a rising spur) and pushed apart when they collide. Without `STAGES`, a column is the longest step count from the Human |
| `STAGES`, `STAGE_ORDER`, `STAGE_LABELS` | optional, for the branch layout. `STAGES = {"cat.event": "stage"}` says the funnel stage of an event; `STAGE_ORDER = ["acquisition", ...]` is the order of the stages, left to right; `STAGE_LABELS = {"acquisition": "aquisição"}` (optional) is the header's text, the name as written in `STAGE_ORDER` otherwise. A stage is a band of columns with a faint header at the top; a station sits in its stage's band, ordered inside it by the path; a station with no entry takes its parent's (or predecessors') stage; an edge back to an earlier stage is a loop (dashed). All three travel to the page in the model payload |
| `TRANSITIONS` | optional `{"cat.event": ["cat.event", ...]}`: the edges, when the process branches or loops (UML statechart transitions); replaces the derived chain; a target may be a dict `{"cat.event": "command"}` to name the command of each edge when one event has several commands |
| `HUB` | optional `"cat.event"`: every start leads to it and it opens every other category (Domain.Updated) |
| `DOMAIN_DRAFT` | optional path of the domain draft (default `<SOURCE stem>_draft.py`) |
| `COST_CENTER` | optional: the id of the cost center this domain's time is billed to (a center of the Costs journal); it turns on the money bar (see the skill's Money bar); without it the journal's `domains` lists decide |
| `HOME` | optional `("category.event", "WidgetName")`: the widget the Visão tab opens with |
| `MODULE_ALIASES` | optional `{"<old name>": "<module>"}`: a module renamed; `?tab=<old name>` still opens it (the Kanban's `{"Quadro": "Kanban"}`). |
| `MODULE_WIDGETS` | optional `{"<module>": ("category.event", "WidgetName")}`: a module of `TABS` that is one of the project's widgets, drawn full width beside the console's contextual sidebar (the Kanban's `{"Kanban": ("card.created", "Board")}`). The console fetches it like the popup does (the first event of that type) and hides its leading title; its goto key is the first free letter of its name |
| `ENTITY_PARTS` | optional `{"<part title>": "WidgetName"}`: the contextual sidebar of one entity, opened by a click (or Enter, Space) on an element with `data-entity="<id>"` inside a widget module (`data-entity-name` and `data-entity-sub` fill its header). One expandable part per widget, rendered for that entity on the root event (`?task=<id>`; register these widgets on the event every entity has), then the entity's JSON. `?ent=<id>` keeps it open |
| `CONSOLE_HOME` | optional: the module this domain opens at the console's `/` (the Kanban's `"Kanban"`), when its journal has an entity; the first domain that declares it wins; without any, `/` opens the first domain |
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
