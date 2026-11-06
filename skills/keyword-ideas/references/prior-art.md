# Prior art

What others already did for keyword research as an agent skill, and what this one took (skill-smith step 1b,
2026-11-06).

- [thibaultbm/claude-seo-geo · seo-keyword-research](https://github.com/thibaultbm/claude-seo-geo) (Sorank, MIT):
  the method as prose: free sources first (Search Console, autocomplete, People Also Ask), one intent and one page
  per keyword, quick wins from Search Console, cannibalization, a buyer prompt panel for AI answers. Taken: the two
  free sources this skill scripts (autocomplete and Search Console quick wins). Left in the public skill, installed
  as it is in the `via-ads` profile: the keyword map and the prompt panel, which it maintains.
- [coreyhaines31/marketingskills · seo-audit](https://github.com/coreyhaines31/marketingskills/tree/main/skills/seo-audit)
  (MIT): "striking distance keywords" and "low CTR" as named audit triggers. Taken: the two names and the idea that
  both come from Search Console, not from a paid tool.
- The literature's names: *striking distance* (positions roughly 4 to 20, a practitioner term, not Google's) and the
  *alphabet soup* expansion of autocomplete (seed + each letter). The thresholds here are flags for that reason.
- Search Console skills on GitHub (`yevgavrikov/claude-skill-search-console`, `coffeegrind123/search-console-skill`
  and others): raw reads of the API, which our `search-console` already does. Nothing new to take.
- Hermes `optional-skills` and Anthropic's [skills](https://github.com/anthropics/skills): nothing on keywords.
- Google Ads and Meta Ads skills seen for later, when the accounts exist:
  [itallstartedwithaidea/google-ads-skills](https://github.com/itallstartedwithaidea/google-ads-skills),
  [boringmarketer/meta-ads-skill](https://github.com/boringmarketer/meta-ads-skill),
  [labofideas/ads-skills](https://github.com/labofideas/ads-skills) and marketingskills' `ads` and `ad-creative`.
