---
name: shape
description: >-
  Use for any request to build, write, change or decide something: the default planning door. Shapes the work before
  anyone builds it (Shape Up): reads the context, routes to the right planning tool for the kind of request
  (brainstorm, the outcome questions, interview, the domain graph, service design, design-taste), then the backbrief
  (mandatory) and the choice of resources; it never executes nor delegates: whoever called it opens the subagent,
  thread or card. Triggers "shape", "planeja",
  "plan", "vamos fazer", "quero", "faz", "nova tarefa", "brainstorm", "backbrief". Questions and one-line commands skip
  it.
metadata:
  version: 0.5.0
  license: MIT
---

# shape

The owner's job is to plan; the agents build. `shape` is the one planning skill the agent uses by default; the others
are its pieces.

**The name.** *Shaping* is Ryan Singer's term in *Shape Up* (Basecamp, 2019): give the work its form (the problem,
the appetite, the solution's outline, the rabbit holes) before betting on it and handing it to the team. Ours is the
same cycle: shape, backbrief, delegate. It is a verb because the skill is an act, and `plan` was taken.

**A compound skill.** Like a *compound AI system* (Zaharia et al., BAIR, 2024: a result from several components
working together instead of one model), `shape` holds no method of its own besides the outcome questions: it routes
to pieces that stay separate skills, each with its own file, version and tests. The pieces are slash-only
(`disable-model-invocation: true`, Claude Code's field: the skill leaves the model's index, `/name` still works); in
Hermes, which has no such field, their descriptions say "a piece of `shape`" and the triggers live here. `shape` loads
a piece by name (`skill_view`) or by its file (`../<piece>/SKILL.md`).

## Steps

1. **Context first.** Read what already answers the request: the Kanban card (`kanban.sh show`), the task's domain
   in the dev-console (`/domain/<slug>`), the reports, the `.wiki`. Ask only what is still missing.
2. **Route by the kind of request** (one row, sometimes two; never all):

   | The request | The piece |
   |---|---|
   | the idea is still open ("vamos pensar", "não sei o que quero") | `brainstorm`: Double Diamond, systems thinking |
   | it names a thing without a number ("faz um site") | **Pelo resultado**, below, through the ask tool |
   | many decisions, or decisions that need images, code or tables | `interview` (opens inside the dev-console) |
   | a screen, a flow, a service | `domain-plan` (the domain graph) and service design (blueprint: the person's steps, the front stage, the back stage) |
   | taste and quality (business, product, interface, software, writing) | `design-taste`, the facet that fits |
   | clear and small | straight to step 3 |

3. **Backbrief, always** (`backbrief`): the teach-back the owner confirms. Nothing is built before the ok. It has a
   ceiling: on the owner's 2nd adjustment the shaping opens a line of understanding instead of guessing a 3rd time
   (see *O melhor caminho*).
4. **Executable acceptance before code.** For implementation work, include `doctor-driven` in the handoff. The executor writes the nearest `.doctor.yaml` before implementation, observes and confirms a relevant red, and includes a journey for capabilities with real users. Existing CI gates stay in place.
5. **Choose the resources** (`shape.sh choose '<kind>'`): the least-cost combination, "Decidi X porque Y".
6. **Hand back.** Shape ends here: the shaped request plus the recommended form ("Decidi thread porque…",
   `resources.chosen`). Shape never opens a thread, a subagent or a card (no `thread.sh`, no `delegate_task`, no
   `kanban.sh pull`): the caller (the Bili, or the agent that loaded it) executes and emits `work.delegated`.
## Pelo resultado (a coisa nomeada sem número)

Use this mode when the request **names a thing** (site, landing, página, app) or **has no measurable outcome**
("faz site pro Via Corretor"). Every task is asked by its outcome, not the thing: the thing is the means. The names
come from the literature: *commander's intent* (Mission Command: say the why and the end state, not the steps),
*Impact Mapping* (Gojko Adzic: goal, who, impact, deliverable) and *Fit for Purpose* (David Anderson: a weekly
review of whether the number moved). The house's record is `.wiki/fit-for-purpose.md` in `~/biliboss`.

1. **Context first.** Before asking anything read what already answers it: the task's domain (`/domain/<slug>`),
   the reports (Search Console, analytics, the Costs journal), the Kanban cards (`kanban.sh list`, `show`). Ask only
   what is still missing.
2. **One ask call, at most 5 questions, the recommended option first in each**, built from what the context showed.
   The first is always the outcome: *"Daqui a 90 dias deu certo: o que mudou?"* (options are numbers the context
   makes plausible). Then, only if missing: para quem, qual número (with source and deadline) and the limits. The last
   is always the cheapest path: *"Se só desse para fazer uma coisa nesta semana, qual mexe mais o número?"*.
3. **The output is a high-level request with 5 fields, plus the week's bet:**

   ```
   Por quê: <the result the owner wants, one line>
   Para quem: <the person it serves>
   Resultado: <number, source, deadline; today's value when known>
   Limites: <what must not happen>
   Pronto quando: <what the source shows>
   Aposta da semana: <the one cheapest move on the number>
   ```

   Limits skipped by the owner mean the house's: the 4 cases (money, login, publish, delete) and the LGPD.
4. It goes through the normal gate: this text is the repetition (`understanding.taught_back`, step 3 of Explain),
   confirmed as usual. Once confirmed, it becomes the card's description:
   `kanban.sh describe <card> --file <path>` (the title is the *Por quê*; one card per piece of work, in Upstream).
   The optional `intent` object of `understanding.taught_back` carries the same fields
   `{why, who, result, limits, done_when, bet}`.

Worked example. *"faz site pro Via Corretor"*: the context says the domain Via Blog gets 14 clicks a month and no
signup is measured, so the first question is the outcome with *"cadastros por mês vindos do blog"* recommended.
The request that comes out:

```
Por quê: o Via ganhar corretores pela busca do Google, sem pagar anúncio.
Para quem: o corretor autônomo de Jundiaí.
Resultado: cadastros por mês vindos do blog (ref=blog), medidos no domínio Via Blog; hoje 14 cliques por mês e nenhum cadastro medido; prazo de 90 dias.
Limites: nada publicado sem o ok do Gabriel; sem gasto com anúncio; nenhum dado para fornecedor (LGPD).
Pronto quando: o domínio Via Blog mostra cadastros com ref=blog subindo por 4 semanas seguidas.
Aposta da semana: melhorar o blog que já traz gente pela busca (CTR de como-tirar-creci de 0,43% para 1,5%).
```

The cheapest path was not a new site: the blog that already gets people.

## In the dev-console

The domain `shape` (`/domain/shape`) lists every shaping, one line each: request · piece · attempts (1/3, 2/3, ⇡ line) · est vs real cost · state; burgundy only for
what waits for the owner (a backbrief not yet confirmed). The agent writes it through `scripts/shape.sh`:

```
shape.sh emit request.received '{"text":"..."}' --shaping <id> --actor <who>
shape.sh emit piece.routed '{"piece":"brainstorm"}' --shaping <id> --actor <who>
shape.sh emit understanding.taught_back '{"text":"..."}' --shaping <id> --actor <who>
shape.sh emit understanding.confirmed '{"text":"ok"}' --shaping <id> --actor <who>
shape.sh emit work.delegated '{"to":"subagent"}' --shaping <id> --actor <who>
shape.sh emit backbrief.attempted '{"n":1}' --shaping <id> --actor <who>
shape.sh emit understanding.line_opened '{"tool":"clarify"}' --shaping <id> --actor <who>
shape.sh choose code-change --shaping <id>
shape.sh emit shaping.closed '{"real_minutes":12,"real_cost_brl":3.5}' --shaping <id> --actor <who>
shape.sh learn
shape.sh list [--status taught_back]
```

Pieces: brainstorm, pelo-resultado, interview, domain-plan, design-taste, direct. Delegations: subagent, thread, card.
Journal: `~/.local/share/shape/events.jsonl` (override `SHAPE_DIR`).

## O melhor caminho

Shape picks the cheapest path to a good result, and learns what each path really costs.

**1. The backbrief loop.** `understanding.taught_back` stays valid (one per teach-back); `backbrief.attempted {n}` counts
them (n = 1, 2). The owner adjusts the first time: teach back again (`n=2`). He adjusts a 2nd time: attempt 3 does
not exist (`shape.sh` refuses `n=3`); emit `understanding.line_opened {tool: clarify|interview}` and ask there
(`clarify` for one or two open points, `interview` for many) instead of guessing again. The line needs 2 attempts in
the journal first. The HOME line shows `1/3`, `2/3` or `⇡ clarify`.

**2. The catalog.** One file, `references/resources.json` (fields in `references/resources.md`): every house skill,
the Hermes profiles (hacker, hipster, sre, hustler, via-ads, mantainer), the models (haiku, sonnet, opus) and the
forms (subagent, thread, card, `--here`), each with `what_for`, `est_minutes`, `est_tokens`, `est_cost_brl` (owner
time at R$ 190,48/h when he is involved) and a `source`: `journal:<path> n=<k>` when computed from a real journal
(`scripts/catalog_seed.py` reads costs, tasks, brainstorm and the Hermes delegation transcripts), else `estimate`.
Unknown is `estimate`, marked; never invented as measured.

**3. The choice.** `shape.sh choose '<request kind>'` (code-change, small-edit, idea-open, interface, ops, later)
prints the least-cost combination, one option per slot (planning, form, profile, model), as "Decidi X porque Y". With
`--shaping <id>` it also emits `resources.chosen {resources, est_minutes, est_cost_brl, why}`.

**4. The learning.** When the work ends, `shaping.closed {real_minutes, real_cost_brl}`. `shape.sh learn` (the
`--learn` modifier, and automatic once 10 shapings closed since the last learn) compares estimated vs real for each
resource of every newly closed shaping, moves the estimate by a moving average (`alpha` 0.3 in the catalog),
rewrites `resources.json` with the source updated, prints the diff and opens a PR with it (gh-app; `--no-pr` skips).

**Origin.** It is the `retro` loop applied to cost: retro turns the owner's corrections into rules; here the gap
between the estimate and what it took turns into numbers, so the next choice starts closer to the truth.

## Writing for the owner

Every question and backbrief goes to the owner as a form he clicks, never as an options list typed in chat: the ask
tool when the session has one, else the `interview` skill (it opens in the dev-console Browser). He rejects the chat
list as verbose. The chat line that goes with it is one sentence ("o backbrief está no console"). Inside the form,
short paragraphs with a blank line between them, and the recommended option first. A backbrief is one ask call: what was found in the context, the plan in numbered steps, the decisions taken ("Decidi X
porque Y"), "Pronto quando", then "Bate?" with the choices (approve first, a variant, "Não ficou bom"). A wall of
text in one paragraph gets sent back for formatting before it is read.

**Shaping a feedback file** ("o último arquivo em Downloads é um feedback, shape it"): read it (`read_file` extracts
.docx and .pdf), then map it point by point onto the brief and the plan it reviews: what it approves ("ok"), what
it changes (a rename, a merged or dropped screen, a new metric) and what conflicts with an earlier source (a
spec's method replaced). The backbrief form opens with an `info` question that lists "what I understood" page by page,
then the plan question (approve first), then one question per conflict with the recommendation, and last a text
question for who wrote it when the file does not say. Nothing in the LP, the screens or the wiki changes before the ok.

When the owner gives a principle mid-work ("o sistema deve experimentar", a new rule for the process), it enters the
open shaping's backbrief, or the next one, as a numbered point; it is not built on the side.

## Pitfalls

- Shaping is not doing: no file is written before the backbrief's ok.
- Shape does not execute nor delegate: it never opens a thread, a subagent or a card. It recommends the form;
  the caller opens it and emits `work.delegated` (the cost learning still closes).
- One row of the router, not a tour of every piece: the piece is chosen by the request, and a clear request skips
  step 2.
- A piece is never called on its own by the agent; the owner can, by `/name`.
- Name the shaping yourself: `request.received` takes `--shaping <slug>` (the thread's topic or the card's slug);
  `emit` does not print a usable id back, so a shaping started without one cannot be continued by the next emit.
- A backbrief the owner already approved (a thread brief saying so) still gets its events: emit request.received,
  piece.routed, understanding.taught_back and understanding.confirmed (actor owner) before delegating, or the shaping
  is missing from `/domain/shape` and from the learning.
- Close every shaping with `shaping.closed` and real numbers, and record in `resources.chosen` what actually ran
  (not what `choose` recommended, when they differ): `learn` moves the estimates of the resources it finds there.
