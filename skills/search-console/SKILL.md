---
name: search-console
description: >-
  Read Google Search Console data for a site through a read-only service account. Lists the properties, the search
  analytics (clicks, impressions, CTR and position by query, page, date, country or device over a window), the
  sitemaps and a URL's index status, as JSON from scripts/gsc.sh. Use when the owner or the Ads agent asks "como está
  a busca orgânica", "quais consultas trazem clique", "a página X está indexada", "Search Console da Via",
  "impressões e posição", "o sitemap foi lido". Not seo-keyword-research (finding new keywords outside our data) and
  not the Mkt Dash (paid media).
metadata:
  version: 0.1.0
---

# search-console

Everything goes through `scripts/gsc.sh` (logic in `gsc.py`, uv PEP 723, read-only scope `webmasters.readonly`).

```sh
G=<skill>/scripts/gsc.sh
$G sites                                              # the properties the service account can read
$G query [--days 28] [--by query|page|date|country|device] [--limit 25] [--filter page~/blog | query=imóvel]
$G sitemaps                                           # submitted sitemaps, last read, errors
$G inspect <url>                                      # index status, canonical, last crawl of one URL
```

- **Credentials**: `GSC_KEY` is the service-account JSON (default `~/.config/biliboss/via-ads-gsc.json`, mode 600, never
  in git); `GSC_SITE` is the property, `sc-domain:<domain>` for a domain property. A Hermes profile sets both in its
  `.env`. Where each key lives: the house wiki's `segredos` page.
- **Access is granted in Search Console, not in Google Cloud**: the service account's e-mail must be added as a user
  (Restricted is enough) under the property's Settings → Users and permissions, by an owner. The API cannot add
  users. Without it every call on the site answers 403 and `sites` is an empty list.
- **The window ends two days ago**: Search Console data lags about two days, so `--days 28` is the 28 days up to then.
- Report numbers as the tool returns them (clicks, impressions, CTR as a fraction, average position); compare windows
  by running `query` twice, never by guessing a trend from one window.
- Read-only by design: submitting a sitemap or requesting indexing needs another scope and is a decision for the
  owner, not this skill.
