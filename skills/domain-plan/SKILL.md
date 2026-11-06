---
name: domain-plan
description: >-
  A piece of `shape` (only by /domain-plan): draw the task's domain in the dev-console (events, and above
  each event the screen a person sees), mark draft or real, and detect drift between drawing and code; the
  drift list is what Downstream builds. `shape` calls it when the request is a screen, a flow or a
  service; also run on a card entering Upstream.
disable-model-invocation: true
metadata:
  version: 0.4.0
---

# domain-plan

Upstream is planning (Upstream Kanban, Steyaert 2018). The plan is the **desired state** of the task's domain; the code is
the **actual state**; `drift` is the difference, and the difference is the work. The owner approving the plan is the
commitment point: the card goes to Downstream and Downstream builds the drift list.

## Steps

1. **Find the domain in the dev-console** (`devc domains`). If it is missing, import it from the code first (skill
   `dev-console`, "Import a domain from existing code": `Domain.Imported`, the project file outside the product repo, one
   file `<name>_events.py` with the `EVENTS` the code records, each traced `# kind: X` to file:line), register it
   (`console.sh domains add <file>`) and adjust it. Never draw a plan over a domain nobody imported.
2. **Open the plan**: `scripts/plan.sh start <slug> --repo <repo> --domain <domain> --events-file <path to the
   <name>_events.py> --console-source <the SOURCE the console reads>`. `kanban.sh pull` already does the first half (slug, repo, domain) when it puts a card in Upstream.
   **Then pin the outcome before drawing anything.** Read the plan's documents, the product's wiki on `origin/main`
   (`git show origin/main:.wiki/<moc>.md` and what it lists; the plan branch may be older than main) and who asked for
   the task. Anything that landed on main after the plan opened (a brief, a design system) is a new candidate: record
   it with `plan.sh add --kind document` before asking, or the question offers stale options. Then ask the owner once,
   **through the `interview` skill** (a form with the recommendation pre-selected; it opens in the dev-console Browser when
   the console is up), never as an options list typed in chat: the owner rejects that as verbose and wants to click.
   Recommendation first: the first question is the outcome ("daqui a 90 dias deu certo, o que mudou?", the plan's
   candidates as options), the last compares the scope with the cheapest path this week. With the answer, write the
   high-level request in five fields (por quê, para quem, resultado medido, limites, pronto quando) plus the week's bet,
   on the card (`kanban.sh describe <card> --file <f>` when it exists, else as a plan `document`).
3. **Draw the desired state as drafts**: `plan.sh add <slug> --kind event --name category.event [--command C] [--after
   other.event]`, and **above each event a person sees, its real screen as HTML in the product's look** (cheap UI now:
   build the screen, never describe it): `--kind screen --name <n> --event category.event --file <path in the repo>`
   (or `--url`). Names come from the code and the wiki, never invented; few events, `Updated` per element
   (skill `design-taste`).
   - **Event names come from the wiki's state transitions** (the `De → Para` tables, the real-time and webhook event
     lists): "premiação definida" becomes `award.confirmed`, "pedido emitido" `order.issued`. A screen that only reads
     (a dashboard, a profile, a simulator before it proposes) records no event: hang it on the event it leads to, and
     several screens may sit on one event. Usage of read screens is telemetry, not domain.
   - Put the screens in `<repo>/.plan/<slug>/telas/`, all linking one shared tokens CSS in that folder (the product's
     brand tokens), with the product's fictional demo data; check each at 390 px (`scrollWidth == 390`) before adding it.
   - Draw the **whole version's domain**, not only this week's bet: the bet is a document and an order, the drawing is
     the desired end state.
   - **Then the version's LP** (skill `lp-draft`): it tells the version's story and embeds the drawn screens as its
     showcase; open it with `devc browse`. The owner expects it as part of Upstream, before he approves.
4. **Keep decisions, sources and questions in the plan**, as a `document`: `--kind document --name <n> --text ...
   --decision "Decidi X porque Y" --source <page> --question "<open question>"`. An open choice of the owner is a
   question, not an event.
5. **Run drift**: `plan.sh drift <slug> [--mark] [--json] [--detailed-exitcode]` prints three groups, plus `perdido`
   (marked real, gone from the code):

   | Group | Meaning |
   |---|---|
   | a construir | draft, not in the code |
   | construído | draft the code already has; `--mark` turns it real |
   | fora do plano | in the code, not in the drawing |

6. **Stop after the drift; the owner approves** -> `plan.sh confirm <slug>`, then `kanban.sh move <card> Downstream`.
   Upstream writes no product code: small choices are decided and logged as "Decidi X porque Y" in the plan. Downstream builds the
   `a construir` list and runs `drift --mark` as it lands; a drift that empties is the task done.

## The plan file

`<repo>/.plan/<slug>.jsonl`, one JSON per line (`id, event, at, actor, value`), editable by hand like every prototype
journal of the house. `plan.started {slug, domain, events_file}`, `element.updated {kind event|screen|document, name,
state draft|real, ...}` (one event for create, change and delete: `change: deleted`), `plan.confirmed {by}`. The code
is `scripts/plan.py` (uv, stdlib only); `plan.sh show <slug>` folds it.

Decidi guardar o plano num JSONL no repo (`.plan/`) porque ele viaja com o código e com o PR do plano, e o dono o edita
à mão; o `console_domain_draft.py` do dev-console guarda a *forma* do domínio (classes de mentira), não decisões,
fontes nem telas, então não serve de formato. Decidi desenhar no grafo pelo mesmo mecanismo de rascunho que já existe:
um evento em `EVENTS` sem registro no diário aparece contornado. Decidi ler a realidade com o mesmo `ast` sobre `EVENTS`
que o `console_domain.py` usa, porque assim o desenho não pode divergir do que o console desenha.

## In the dev-console

The console reads `EVENTS` from the project's `SOURCE` with `ast`, so `plan.sh` writes the drafts there: `--console-source`
names a file that is the real events file plus the draft events (each commented "rascunho: só no grafo"), rewritten after
every `add`, `drift --mark` and `plan.sh sync` (run it after editing the JSONL by hand). The project file's `SOURCE` is that
file. No journal records a draft, so the console outlines it (**outlined = not in the code**); once the code records it, it is
filled. `scripts/dev_console_plan.py` (imported by the project file) adds the drafts' `after` edges (`with_edges`) and the
widgets (`widgets(plan_file, WIDGETS)`): **Plano** (the drift) on every event and **Tela** (the screen drawn above the event,
in an iframe) where one sits. `--events-file` stays the real registry: drift reads it, never the merged one.

## Pitfalls

- A drift against an unimported domain is empty noise: import first (step 1).
- `--events-file` must be the real registry. Pointing it at the console's merged file makes every draft look built.
- A project constant named `HOME` shadows the console's `HOME` widget tuple and 500s the page: never name a path `HOME`.
- **An empty domain takes the whole console down.** `plan.sh` refuses an events file with `EVENTS = {}` on one line (the
  closing brace must be on its own line: `EVENTS = {` then `}`), and a registered project whose SOURCE has no events, or
  whose `TRANSITIONS` come only from `plan.with_edges({}, ...)`, makes the console's `derive()` raise StopIteration: 5057
  stopped answering for every domain. Give the project file a base `TRANSITIONS` (the journey) that `with_edges` extends,
  run the adds before `console.sh domains add`, then curl `-L` the domain and `/domain/kanban` for 200.
- The plan lives on the repo's branch until its PR merges; the project file points at the checkout that has it.
  Merge `origin/main` into the plan branch before linking files that landed on main (a brand folder, logos), or the
  screens load with broken paths.
- **Drift counts a screen as built as soon as its HTML file exists**, so screens never sit in `a construir`: the work
  list is the events group; say so in the report instead of reading "construído" as done.
- **Re-adding a document replaces only the lists you pass** (`--question`, `--decision`, `--source`) and keeps the rest.
  To close an answered question, re-add the document with `--question "Respondida em <data>: <answer>"`.
- Tests: `uv run --script scripts/test_plan.py`.
