# Atomic design in the dev-console

The console's widgets are classified by Atomic Design level (atoms, molecules, organisms, templates, pages). The atoms
live in `scripts/console_atoms.py`. A widget is built from them and never hand-writes a title or an empty state.
Audit of 2026-11-06. Paths are relative to `skills/`.

## Levels

| Level | What | Where |
|---|---|---|
| Atom | `title`, `empty` (console_atoms); formatters `_when`, `_brl` | `dev-console/scripts/console_atoms.py`; `_when` x3, `_brl` in cost-track |
| Molecule | one list or one value with its title: `contas`, `cofre`, `task_list`, `worth`, `cost_centers`, `time_entries`, `observation_list`, `observation_log`, `proposal_list`, `linked_items`, `tension_updates`, `card_history`, `card_time`, `journal_stamp`, `modelagens`, `widget_list`, `event_list` | each `*/scripts/dev_console_project.py` |
| Organism | a section with behaviour: `board`, `upstream_band` (kanban), `cost_toolbar`, `day_cost` (cost-track), `causal_loop` (brainstorm), `skill`, `before_after`, `journey`, `task_execution_result`, `domain_diff`, `task_execution_log` (backbrief), `tension_list` (tensions), `toolbar`, `state_graph`, `right_menu`, `domain_switcher`, `code` (dev-console); console: `render_list` (WidgetList), `observability`, `render_screens`, `render_expected`, `_status_bar` | dev-console.py:447-590, 2528 |
| Template | composes organisms: `tension_detail` (`ctx.of`), `domain_view`, `tasks` (backbrief:520), `contas_e_cofre` (auth:89) | |
| Page | the routes: `/domain/<slug>` (`domain`, dev-console.py:2294), `/t/<slug>/<tid>` (`tension`, :2390), home, `/agents`, `/playground` | dev-console.py |

## Duplications found

1. **Widget title**: the same `H2(..., cls="mb-3 font-sans text-base font-semibold ...")` was written 5 times (`_title`
   in kanban, cost-track and backbrief; inline in brainstorm and in `render_screens`). **Migrated** to `title()`.
2. **Empty state**: `P("...", cls="text-neutral-400")` was written 13 times across auth, backbrief (3), brainstorm,
   cost-track, shape, tensions (2), dev-console's project (2) and the console (`_empty`, `render_list`). **Migrated** to `empty()`.
3. **Bordered frame**: `rounded border border-neutral-200 dark:border-neutral-800` appears 11 times, and the `-300/-700` variant
   4 times (dev-console.py:473, 558, 2444; tensions:203). This is the next atom (`frame`), not migrated yet.
4. **Stat number**: `text-2xl font-semibold tabular-nums` appears 5 times (dev-console.py:521-522, and 1462-1464 in JS).
   Next atom candidate (`stat`).
5. **Date formatter** `_when`: 3 copies (dev-console.py:502, kanban:112, backbrief:160), each with a different input type.
6. **Row / badge**: no shared markup repeated across projects yet (the WidgetList row lives only in `render_list`).
   They become atoms when a second copy appears.

## Bypasses

- `domain-plan/scripts/dev_console_plan.py:45,49,52,69`: inline `style="font-size:18px"` titles instead of the title atom.
- `auth:89 contas_e_cofre` and backbrief's `tasks` call sibling widgets directly instead of `ctx.of(...)` / `render_widget_list`;
  only `tensions:68` composes through `ctx.of`.
