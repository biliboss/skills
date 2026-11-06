---
name: hustler
description: >-
  Use when a new project or idea starts, when there is a market question, or when the owner says "hustler", "mercado",
  "posicionamento", "quem são os concorrentes", "onde a gente se encaixa" or "como ganhar dinheiro com isso". Scans the
  market around an idea: the customer's job, the real alternatives (competitors, open source, do-nothing) with sources,
  a positioning map on the two axes the customer cares about, where the upper quadrant is and what it takes to get
  there, and the business model options (including open-core). Writes one wiki page plus the map, and lists what to
  re-check, because it is meant to be re-run. Not for deciding what to build next in a clear task (backbrief) nor for an
  idea still being shaped (brainstorm).
metadata:
  version: 0.1.0
  license: MIT
---

# hustler — always go further in the market

An idea is only as good as its place in the market. This skill is the same routine every time: **know the job, list
who else does it, draw the map, find the empty upper quadrant, price the way in.** Each run starts from the last
page, so the market view only ever grows. Credits and links: [README.md](README.md#créditos-e-referências).

Output language follows the project (Portuguese for the house); names and code in English. Generic by rule: a page
that goes public carries no private numbers or client names.

## Procedure

1. **The job and the customer, one line.** "Help <who> to <job> without <pain>" (Jobs to Be Done: the customer hires a
   product for a job, so name the job, not the product). Include the customer's budget or limit if known; say where it
   came from. If the line will not fit in one sentence, the idea is not ready: use `brainstorm`.
2. **The real alternatives, with sources.** Web search (`web_search`, then `web_extract` on the pricing and product
   pages). Always three kinds: **competitors** (paid products), **open source** (repos, license, last release) and
   **do-nothing** (what the customer does today; usually the strongest rival). Also read the thesis side: the
   Y Combinator *Requests for Startups* (ycombinator.com/rfs) for what funders say they want. Record per alternative:
   name, price, one-line what it does, URL, date read. A number from a vendor's own page is marked as such. Never fill a
   gap with a guess: write "not found" and put it in step 6.
3. **Two axes, one map.** Pick the two things that decide the customer's choice (ask: what makes them say no?).
   Prefer a measurable axis (tasks of the job covered, minutes to start) to a vague one. Score each alternative 0–10,
   mark every score that is not measured as "estimate", and place **us** (bordô, `kind: us`; a target not built yet is
   `kind: target`, dashed). Data goes in `<project>/.wiki/resources/hustler-<slug>.json`; render with
   `scripts/render-map.sh <json> <html>` (one standalone HTML, inline SVG, grays plus the bordô accent, dark and
   light). Open it at ~1100 px and check no label sits on another dot.
4. **The upper quadrant, and the way in.** The upper right is where both axes are high: Gartner's Leaders sit at high
   *ability to execute* and *completeness of vision*; here it is the same shape with the customer's own axes. Say
   whether it is empty, crowded or held by a giant (a platform owner can commoditize a corner). Then use the Blue Ocean
   *four actions* on the gap: what do we **eliminate, reduce, raise, create** against the alternatives to get there?
   Finish with the cheapest test that would prove the gap is real (an interview, a landing page, a prototype).
5. **Business model options.** At least: hosting or subscription, usage or credits, services or setup, and the
   **open-core** option (project open, sell what runs it: hosting, credits, services, paid features; the term is
   Lampitt's, 2008). For each: **who pays what**, a precedent from step 2, and its trap (open-core: say plainly what
   stays open, or contributors and users stop trusting the line).
6. **Write it and list what to re-check.** One page `<project>/.wiki/hustler.md` (job line, alternatives table with
   links, the map, findings, models, the re-check list) and the HTML in `<project>/.wiki/resources/`. Keep
   `findings` to three. The re-check list is mandatory and concrete: every "not found", every estimate to test, every
   source that changes by season (prices, RFS batches, platform rules). Register "Decidi X porque Y" for any choice
   made.

## Re-running ("always go further")

- Read the project's `.wiki/hustler.md` and its JSON first; do **not** start over. Walk the re-check list, update scores,
  prices and dates, add the alternatives that appeared, and move the dots.
- Each run adds one dated line to a "Rodadas" list at the end of the page: what moved, what is new, what is still open.
  If a new alternative lands in the upper quadrant, that is the headline.
- Every third run, challenge the axes themselves: ask whether the customer's reason to say no has changed.

## Pitfalls

- **Search the do-nothing alternative as seriously as the competitors**; a map without it flatters the idea.
- **A vendor's page is a claim, not a measurement**: mark its prices and features "per their page" and its ease
  scores "estimate" until someone tests the product with the customer persona.
- **Never invent a name for a framework or a metric**: use the literature's term and credit it in the README.
- **Keep the page generic if it will be public**: no client names, no private revenue; use a persona.
- **Render, then look.** Open the HTML in a browser before saying done; overlapping labels hide a position.
