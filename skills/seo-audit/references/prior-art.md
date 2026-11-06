# Prior art

What others already did for an SEO audit skill, and what this one took (skill-smith step 1b, 2026-11-06).

- [coreyhaines31/marketingskills · seo-audit](https://github.com/coreyhaines31/marketingskills/tree/main/skills/seo-audit)
  (MIT): the full audit framework as prose (crawlability, indexation, on-page, E-E-A-T, hreflang). Taken: the
  warning that curl cannot see JSON-LD injected by JavaScript (here a `info` with that caveat, never an `erro`), the
  priority order (indexation before on-page), canonical rules (self-referencing, never through a redirect). Left in
  the public skill: the checklist itself, which it maintains.
- [sanity-io/agent-toolkit · seo-aeo-best-practices](https://github.com/sanity-io/agent-toolkit): metadata, Open
  Graph, sitemaps, robots.txt, JSON-LD and EEAT. Taken: the list of tags to read. Installed as it is in the
  `via-ads` profile.
- [Google Search Central](https://developers.google.com/search/docs): title links and snippets are cut by width and
  may be rewritten, canonicalization, sitemaps on another host need cross-site verification or the robots.txt. Taken
  as the source of the findings marked as facts; the 60/160 character limits stay marked as heuristics.
- Hermes `optional-skills`: nothing on SEO (the closest, `productivity/property-listings`, only formats listing
  cards). Anthropic's [skills](https://github.com/anthropics/skills): nothing on marketing.
- What none of them had and this one adds: a script that answers in JSON, so the agent reports numbers it read
  instead of a checklist it recited, and the canonical-loop check, found on the Via's own blog.
