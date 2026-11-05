# The project contract

A project is shown by the dev-console through one Python file, `dev_console_project.py`, that the
console imports (`--project <path>`). The console's environment has FastHTML, so widgets may import it.

| Name | What it is |
|---|---|
| `NAME` | the project's name on the bar |
| `SLUG` | optional: the domain's URL, `/domain/<slug>` (default: the skill folder name) |
| `BASE` | set by the console (`/domain/<slug>`): build every link to the console with it (`f"{BASE}/do/..."`) |
| `SOURCE` | path of the file that holds `EVENTS` (read live with `ast`) |
| `EVENTS` in `SOURCE` | `{category: {command: event}}`, ordered: the first category's first command creates the entity; inside a category each event follows the previous one |
| `ENTITY`, `ENTITY_PLURAL` | what one item of the rail is, singular and plural |
| `ENTITIES` | `{category: entity name}`, for node labels (`Tension.Created`, `Action.Proposed`) |
| `ENTITY_KEY` | the journal field that names the entity (`tension_id`) |
| `PROJECTOR` | the function in `SOURCE` that folds events into the entity; the keys of its dict literal are the properties shown |
| `journal` | object with `read(query)`: `{}` all entities, `{"id": x}` one, `{"id": x, "history": True}` its events, `{"event": e}` events of a type, `{"history": True}` every event |
| `title_of(history, state)` | the entity's title |
| `INITIAL` | optional `["cat.event", ...]`: the events the Human may start with (Domain.Designed or Domain.Imported) |
| `TABS` | optional: the tabs after the fixed Domain tab, in order; absent = Domain only |
| `HUB` | optional `"cat.event"`: every start leads to it and it opens every other category (Domain.Updated) |
| `DOMAIN_DRAFT` | optional path of the domain draft (default `<SOURCE stem>_draft.py`) |
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

A widget with `fn.fake = True` is a design on fake data (or an embedded console screen): the console renders it
before the journal has its event.

A widget's function name is its name on screen (`tension_list` → TensionList) and the first line
of its docstring is its description in the sidebar.
