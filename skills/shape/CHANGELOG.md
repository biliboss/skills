# Changelog

## [0.3.0] - 2026-11-06

### Added
- Backbrief escalation loop: `backbrief.attempted {n}` and `understanding.line_opened {tool: clarify|interview}`; the
  2nd adjustment opens a line of understanding instead of a 3rd guess (n=3 is refused).
- Resource catalog `references/resources.json` (+ `resources.md`): skills, Hermes profiles, models, forms, with time,
  tokens, cost (owner at R$ 190,48/h) and source; real numbers from the journals via `scripts/catalog_seed.py`.
- `shape.sh choose '<kind>'` (least-cost combination, `resources.chosen`) and `shape.sh learn` (`shaping.closed`;
  moving average over estimated vs real; rewrites the catalog, prints the diff, opens a PR; automatic every 10 closed).
- HOME widget shows attempts (1/3, 2/3, ⇡ line) and est vs real cost.

## [0.2.0] - 2026-11-06

### Added
- Dev-console domain `shape` (`/domain/shape`): the journal (request.received, piece.routed,
  understanding.taught_back, understanding.confirmed, work.delegated), `shape.sh emit|list`, tests, one HOME widget
  listing shapings (burgundy for what waits for the owner).

## [0.1.0] - 2026-11-06

### Added
- `shape`, the default planning door (Shape Up): context, a router to the planning pieces, backbrief, delegation.
- "Pelo resultado" (the outcome questions) moved here from backbrief.
- brainstorm, backbrief and domain-plan become slash-only pieces (`disable-model-invocation: true`).
