# Comparison LP — research fan-out to a page

For a landing page that compares N things (frameworks, products, protocols) through one lens.

1. **Write the lens first**, one file in scratch (`LENS.md`): the dimensions as a table (symbol, name, the question to answer per subject), one reference implementation already understood, and the output contract per dimension: present yes/partial/no, concrete API names, one REAL snippet with URL, one-line design choice. Add "never invent APIs; say 'not found' and where you looked".
2. **Fan out one subagent per subject** (group small ones two per subagent to stay ≤ 8), each told to read `LENS.md` and write `<subject>.md` next to it, returning `{file, summary}` via `output_schema`. Name the sources to read (repo via `gh api`, docs site) and the specific features to check, so the child does not wander.
3. **Verify, don't trust**: grep the tables out of every file (`grep -E '^\| *(S|E|…)\b'`) and read the caveats each child listed (docs-only vs source, snippets paraphrased from prose, versions). Carry those caveats into the page.
4. **Write `SYNTHESIS.md` yourself** (the decision step): the matrix with ●/◐/○ and a "born for" column, numbered findings, merge opportunities as "A + B → result", and any new proposal with its open/unverified items stated. This file is the page's only fact source.
5. **Delegate the page** (see SKILL.md "Delegating the page"): matrix interactive (click a column → the finding), one real snippet per subject with its source link, honest gaps in their own section.
6. **Copy the study files** into `$WIKI_HOME/<projeto>/resources/<produto>/estudos/` in the same commit as the page, so the page's claims stay traceable.

A follow-up page on the same study ("now show how X sits on top of all this") reuses the lens and synthesis: fan out only the new questions (X on the lens; which protocol carries which dimension, spec vs what clients implement), then a sibling page that reuses the first page's tokens and links back to it.
