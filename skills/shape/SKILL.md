---
name: shape
description: >-
  Use for any request to build, write, change or decide something: the default planning door. Shapes the work before
  anyone builds it (Shape Up): reads the context, routes to the right planning tool for the kind of request
  (brainstorm, the outcome questions, interview, the domain graph, service design, design-taste), then the backbrief
  (mandatory) and only then the delegation (subagent, thread or card in Upstream). Triggers "shape", "planeja",
  "plan", "vamos fazer", "quero", "faz", "nova tarefa", "brainstorm", "backbrief". Questions and one-line commands skip
  it.
metadata:
  version: 0.1.0
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

3. **Backbrief, always** (`backbrief`): the teach-back the owner confirms. Nothing is built before the ok.
4. **Delegate** by the size: a subagent with a fit-for-purpose model (minutes), a `thread` (a topic that lives on),
   or a card in Upstream (`kanban`, one card per piece of work). Decisions the agent takes itself go as "Decidi X
   porque Y"; only money, login, publishing outward and deleting wait for the owner.

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

## Writing for the owner

Every question and backbrief in short paragraphs with a blank line between them; the recommended option first.

## Pitfalls

- Shaping is not doing: no file is written before the backbrief's ok.
- One row of the router, not a tour of every piece: the piece is chosen by the request, and a clear request skips
  step 2.
- A piece is never called on its own by the agent; the owner can, by `/name`.
