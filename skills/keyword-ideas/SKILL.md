---
name: keyword-ideas
description: >-
  Find what to target in search from free sources, read-only, as JSON: scripts/suggest.sh asks Google's autocomplete
  in Portuguese what people type after a seed (optionally the alphabet and the question words), and
  scripts/opportunities.sh reads our own Search Console through the search-console skill and lists the queries in
  striking distance (position 4 to 20) and the queries and pages with many impressions and few clicks. Use when the
  owner or the Ads agent asks "que palavra-chave usar", "sobre o que escrever", "o que as pessoas buscam sobre X",
  "onde estamos quase na primeira página", "qual página aparece e não recebe clique". Not search-console (raw numbers
  of one window) and not seo-audit (the tags of a page).
metadata:
  version: 0.1.0
---

# keyword-ideas

Two read-only scripts; the logic is `scripts/kw.py` (uv, stdlib only). Output is one JSON document.

```sh
K=<skill>/scripts
$K/suggest.sh <seed> [<seed> ...] [--expand] [--hl pt-BR] [--gl br]
$K/opportunities.sh [--days 28] [--min-impressions 20] [--max-ctr 0.02] [--limit 1000]
$K/test.sh                       # offline test: fake gsc.sh, autocomplete from a local file
```

## suggest: what people type

- Google's autocomplete (`suggestqueries.google.com`, free, no key) for each seed, in pt-BR and Brazil by default.
  `--expand` also asks `<seed> a` … `<seed> z` and `como|quanto|qual|onde|quando|por que|o que|melhor|vale a pena
  <seed>`: about 30 calls per seed, paced.
- A suggestion is kept only when it holds every word of the seed (accents and case ignored): the probes also bring
  other languages ("como creci" → "como crecio china"). `dropped_without_seed` counts what went out.
- `question: true` marks the questions: they are the titles and the FAQ entries of a post.
- Autocomplete says what people **type**, not how many: no volume. Rank by what our Search Console already shows, or
  say there is no volume; never invent one.

## opportunities: what our data says to do

Runs `gsc.sh query --by query` and `--by page` of the `search-console` skill (`SEARCH_CONSOLE_SH`, else the sibling
skill in the same plugin), so the key and the property are the ones that skill reads (`GSC_KEY`, `GSC_SITE`, or the
Hermes profile's `.env`).

- `striking_distance`: average position above 4 and up to 20, with at least `--min-impressions`. The page already
  ranks; a better title, a section answering the query or an internal link can bring it to the top of page one.
- `low_ctr_queries` / `low_ctr_pages`: position up to 10, impressions at or above the minimum, CTR below `--max-ctr`.
  People see it and do not click: rewrite the title and the description for that query (or the page is answering
  another intent).
- The thresholds are flags, and their defaults are heuristics, not Google's: say which ones you used. Report the
  window (`from`, `to`) with the numbers; to call a trend, run it again on the previous window and compare.

## Related

- `search-console` (the numbers), `seo-audit` (the page's tags: run it on a low-CTR page before rewriting).
- Public, installed as they are: `seo-keyword-research` (Sorank: the keyword map, intent, cannibalization and the
  AI prompt panel; load it to turn these lists into a plan) and `seo-aeo-best-practices`.
  Prior art: [references/prior-art.md](references/prior-art.md).
