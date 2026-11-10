# Attribution

wiki is original writing, with one exception: `scripts/map.py` is derived from Luiz Ribeiro Coelho's `mapear.py` (viacorretor/the-viacorretor#143), itself an adaptation of kingbootoshi's Cartographer (MIT). Beyond it, the skill copies no code from the projects below; it builds on their ideas and on the shape of its sibling skill. This page gives the credit.

| Source | What wiki-smith took |
|---|---|
| Ward Cunningham's [WikiWikiWeb](https://en.wikipedia.org/wiki/WikiWikiWeb) (1995) | The origin of the word and the idea: pages that anyone edits and that link to each other, kept by the people who use them |
| Andrej Karpathy's ["LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) idea file (gist, April 2026; the gist has no pinned revision here because the GitHub API did not answer when it was checked) | The pattern of an LLM that incrementally builds and maintains a persistent, interlinked markdown wiki instead of re-deriving answers every time, with ingest, query and lint as the operations |
| The commonplace book tradition | Keeping notes by date as a record of what happened, apart from the organised knowledge (here: the diary versus the topic pages) |
| Maps of content, from Nick Milo's [Linking Your Thinking](https://www.linkingyourthinking.com) | The map of content: a note that mostly links to other notes, as the hub of a subject |
| [skill-smith](https://github.com/biliboss/skill-smith/tree/481f8239b04d59d4d017b945699788660750a3bb) (`481f823`), same author | The structure and tone of the repo: SKILL.md with routing and steps, `references/`, its own `.wiki/`, CHANGELOG, ATTRIBUTION |
| The [Agent Skills specification](https://agentskills.io/specification) | The SKILL.md format and frontmatter |
| [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) | The changelog format and the version policy |
| [Cartographer](https://github.com/kingbootoshi) by kingbootoshi, MIT | The code-map method that became the skill's map mode: measure the repo, split it into token-budget groups, explore each with a subagent, write the blueprint page |
| Luiz Ribeiro Coelho's adaptation in [viacorretor/the-viacorretor#143](https://github.com/viacorretor/the-viacorretor/pull/143) (`mapear.py`, plus the create/update two-mode method) | `scripts/map.py` is derived from his code — tracked files via `git ls-files`, tokens as bytes/4, the ignore lists — and the map mode's create/update flow is his |

The method in [references/method.md](references/method.md) and the scripts are a generalisation of a working practice in the author's own repositories.
