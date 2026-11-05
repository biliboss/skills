# The project contract

A project is shown by the dev-console through one Python file, `dev_console_project.py`, that the
console imports (`--project <path>`). The console's environment has FastHTML, so widgets may import it.

| Name | What it is |
|---|---|
| `NAME` | the project's name on the bar |
| `SOURCE` | path of the file that holds `EVENTS` (read live with `ast`) |
| `EVENTS` in `SOURCE` | `{category: {command: event}}`, ordered: the first category's first command creates the entity; inside a category each event follows the previous one |
| `ENTITY`, `ENTITY_PLURAL` | what one item of the rail is, singular and plural |
| `ENTITIES` | `{category: entity name}`, for node labels (`Tension.Created`, `Action.Proposed`) |
| `ENTITY_KEY` | the journal field that names the entity (`tension_id`) |
| `PROJECTOR` | the function in `SOURCE` that folds events into the entity; the keys of its dict literal are the properties shown |
| `journal` | object with `read(query)`: `{}` all entities, `{"id": x}` one, `{"id": x, "history": True}` its events, `{"event": e}` events of a type, `{"history": True}` every event |
| `title_of(history, state)` | the entity's title |
| `WIDGETS` | `{"category.event": [fn, ...]}`; `fn(ctx) -> component` |

`ctx` (an `EventContext`): `event`, `focus` (the real event rendered), `entity_id`, `events` (that
entity's events of this type), `state` (the projected entity), `journal_events` (this type in the
whole journal), `entities` (every entity, with `title`).

A widget's function name is its name on screen (`tension_list` → TensionList) and the first line
of its docstring is its description in the sidebar.
