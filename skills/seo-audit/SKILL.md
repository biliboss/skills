---
name: seo-audit
description: >-
  Audit a site's on-page and sitemap SEO from the raw HTML, read-only, as JSON from scripts/audit.sh and
  scripts/sitemap.sh: status and redirects, title, meta description, canonical (and whether it loops back through a
  redirect), noindex, h1, lang, viewport, Open Graph, JSON-LD types, images without alt; the sitemaps from robots.txt,
  their hosts and every URL's status. Use when the owner or the Ads agent asks "audita o SEO do site", "por que esta
  página não aparece no Google", "o canonical está certo", "o sitemap está ok", "o link sai sem imagem no WhatsApp",
  "checa as meta tags". Not search-console (what Google measured: clicks, positions, index status) and not
  keyword-ideas (what to write about).
metadata:
  version: 0.1.0
---

# seo-audit

Two read-only scripts; the logic is `scripts/audit.py` (uv, stdlib only). Output is one JSON document; every page or
sitemap carries `findings`, each `{level: erro|aviso|info, code, text}`.

```sh
A=<skill>/scripts
$A/audit.sh <url> [<url> ...]                 # on-page facts and findings, per URL
$A/sitemap.sh <site|sitemap url> [--check] [--max 200]   # sitemaps from robots.txt; --check GETs every URL
$A/test.sh                                    # offline test on fixtures (local port, no network)
```

## How to read and report

- **Lead with the `erro` findings, then `aviso`**; `info` only when it explains something else. One short line per
  finding, in the owner's words, with the page and what to change. Do not report a passing check.
- **Group what repeats.** The same finding on many URLs (a whole sitemap redirecting, every post with the same
  canonical problem) is one line with the count and an example, never one line per URL.
- **Confirm with Google before calling it a problem in production**: `search-console` `inspect <url>` shows the
  `googleCanonical`, the `userCanonical` and the coverage. The audit says what the HTML asks for; the inspection says
  what Google did with it.
- **It reads the HTML without JavaScript** (`source: html-sem-js`). An app that renders in the browser shows no h1,
  few words and no JSON-LD here even when the rendered page has them: say so instead of reporting them as missing,
  and check the rendered page (Rich Results Test, or the browser tools) before recommending a change.
- **Lengths are heuristics.** Google cuts the title and the snippet by pixel width and may rewrite both; the 60 and
  160 character marks are practitioner rules, not Google's, and the findings say so.
- `canonical-loop` (the canonical points to a URL that redirects back) and `sitemap-other-host` are the costly ones:
  Google gets two contradictory signals and may index both versions or pick the wrong one.

## Limits

- Read-only, and it changes nothing: fixing a tag, the robots.txt or the sitemap is a change in the site's code and
  a decision for the owner.
- It only opens http(s). The URLs it follows come from the pages (redirects, canonical, the sitemap's `<loc>`), so an
  internal or loopback address is refused unless you passed that host yourself; bodies are cut at 10 MB.
- No Core Web Vitals, no crawl of links beyond the sitemap, no hreflang validation (only listed). For the full
  checklist and the "why", load the public skills below.

## Related

- `search-console`: what Google measured and indexed; `keyword-ideas`: what to target.
- Public, installed as they are (the house rule: public before our own): `seo-aeo-best-practices` (Sanity:
  metadata, JSON-LD, EEAT, AI answers) and the `seo-audit` of
  [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) for the full audit framework.
  Prior art and what was taken: [references/prior-art.md](references/prior-art.md).
