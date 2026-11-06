# resources.json

The catalog `shape.sh choose` reads and `shape.sh learn` rewrites. One file; `resources` is keyed `kind:name`
(`skill:`, `profile:`, `model:`, `form:`).

| Field | Meaning |
|---|---|
| `what_for` | one line: when to reach for it |
| `est_minutes` | wall-clock minutes it adds (when `owner_involved`, the owner's minutes) |
| `est_tokens` | tokens it typically burns |
| `est_cost_brl` | R$ per use: owner time at `owner_rate_brl_h` (R$ 190,48/h) when `owner_involved`, else tokens x `meta.machine_brl_per_token`; models carry a flat estimate |
| `owner_involved` | the owner's time is part of the cost |
| `source` | `journal:<path> n=<k>` when computed from real data (`scripts/catalog_seed.py`; ` + shape n=<k>` once `learn` blended in shapings), else `estimate` |
| `learned_n` | shapings blended in by `learn` |

Around it: `request_kinds` (each kind lists, per slot, the options `choose` ranks by R$ then minutes) and `learn`
(`alpha` of the moving average, `closed_seen` = closed shapings already learned, `every` = auto-learn threshold).
`estimate` entries are guesses, not measurements: they only get a journal source after `learn` sees real closures.
