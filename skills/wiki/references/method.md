# The method

How a project's wiki is organised and maintained: `<projeto>/`, one folder per project inside the central `$WIKI_HOME` checkout (default `~/wiki`, the `biliboss/wiki` repo). A few repos instead keep a local `.wiki/` at the root, operated with `-w <repo>/.wiki`; it follows the same rules. File and folder names below are the defaults; a project overrides them in `wiki.config` ([config.md](config.md)). When the project's own wiki says otherwise, the project wins.

The wiki is the agents' memory: they read it, and they keep it. The idea of an LLM that incrementally maintains a persistent, interlinked markdown wiki, instead of rediscovering things on every question, is Karpathy's ([ATTRIBUTION.md](../ATTRIBUTION.md)); the shape below is a working practice built on it.

## What each thing is

| File | Kind | Purpose | Who touches it |
|---|---|---|---|
| `index.md` | root map | every page, one line each, plus the maps | whoever creates or renames a page |
| `moc-*.md` | map of content | the hubs by subject; a page may be in several | whoever creates a page of the subject |
| topic pages (`billing.md`, `security.md`...) | the knowledge | how we work today, one page per subject | whoever changes how we work |
| `inbox.md` | the diary's door | how to write a note, a summary of the last 7 days, highlights, the archive | whoever opens a new day or records something that changes how we work |
| `journal/YYYY-MM-DD/HHMM-slug.md` | diary | what happened, one note per file | any agent that does something big |
| `journal/YYYY-MM-DD.md` | day index | the day's notes, one line each; **generated** | only `scripts/day-index.sh` |
| `resources/`, `assets/` | attachments | HTML fragments and images that pages cite | whoever cites them |

The diary is what **happened**; the topic page is what **holds**. A lesson only in the diary is lost.

## Consulting

1. `rg -n -i '<word>' "$WIKI_HOME/<projeto>"`, or the index list; read only the matching page or section.
2. For what happened: the inbox (short) and only the days that matter. For a date: its day index, then only the notes that matter (a whole day: `cat "$WIKI_HOME/<projeto>"/journal/YYYY-MM-DD/*.md`).
3. For what the system promises (requirements, scenarios), if the repo keeps specs: `rg -n -i '<word>' <specs>`.

## The diary

**When:** a decision, a delivery, a change of course, an incident, a piece of research. Not an intermediate step, and not what a commit already says with nothing to add.

**Where:** a new file `journal/<today>/<HHMM>-<slug>.md`, day and time in UTC. The slug is the title lowercased, without accents, letters, digits and hyphens only, at most 6 words (`1305-the-receiver-starts.md`); if the name exists, add `-2`. Then regenerate the day index. Several agents can write the same day, each on their branch, without touching the same file. Never rewrite another's note.

**The note:**

```
## HH:MM — <title that says what changed>

One well-written paragraph: what happened, why it matters, where the evidence is (commit, PR, issue),
with a link to the topic page. Links are relative to the day folder: [billing](../../billing.md).
```

The time is UTC and equals the one in the filename. The date is not in the title (it is in the folder name). Old notes with no time are named `no-time-<slug>.md`.

**The day index** (`journal/YYYY-MM-DD.md`) is generated: a title, a map line (inbox, previous day, next day) and one line per note in filename order. Never edit it. A merge conflict there: run `scripts/day-index.sh` again (a `merge=union` rule in `.gitattributes` for `journal/*.md` keeps both sides' lines in a local merge).

**First note of the day:** the generator creates the index; add the day at the top of "last days" in the inbox.

**The inbox, the door:**
- When recording something big, update the day's line in "last days": one sentence with the day's main point.
- If the note changes how we work, it also gets a line in "highlights".
- When a day is older than 7 days, its line moves to "archive" and stays there.
- No note is ever written in the inbox.

## Ingest: from the diary to the page

Every note carrying a rule, a lesson or a lasting fact also changes the topic page, in the same session:

1. Find the page (`rg`). If it does not exist and the subject will return, create it; if it is small, put it in a section of a nearby page.
2. Write the rule **as it holds now**, without the history (the history stays in the diary). Example: the page says "before creating a card, search for existing ones"; the diary tells about the duplicate that taught it.
3. If the page said the opposite, correct it; do not accumulate "it used to be".
4. The diary note points to the page.

## Create, rename, delete a page

- **Name:** one subject, lowercase with hyphens (`agent-inbox.md`). The title (`# ...`) says the subject and its scope; the first sentence stands alone: what it is and what it is for.
- **A new page gets:** the dates (`scripts/dates.sh`), one line in the index (`[name](name.md): what it has`), a place in at least one `moc-*`, and the footer:

  ```
  ---

  Map: [moc-x](moc-x.md) · Related: [a](a.md) · [b](b.md)
  ```

- **Short:** past about 150 lines, or when kinds mix (rule, procedure, reference, history), split into sections by kind or into child pages.
- **Rename:** change the links that pointed to it (`rg -l 'old-name' "$WIKI_HOME/<projeto>"`), anchors included.
- **Delete:** only when the content already moved to another page; swap the links to it.

## New subject: a map and its facet pages

When a subject has several facets and will come back, one page would mix kinds. Build a map (the idea of a "map of content" is Nick Milo's, see [ATTRIBUTION.md](../ATTRIBUTION.md)):

- `moc-<topic>.md`: an opening paragraph (what it is, where it lives, what it replaces or sits next to), **the pages** (one line each, the cheatsheet first), **what to know first** (the few rules that bite, each with a link to the page that explains it), the footer.
- `<topic>-<facet>.md`, one per facet. A good first set: **cheatsheet** (addresses, ids, commands, shortcuts; the page you open first), **install** (how it is set up, how to update and back up), **integration** (how agents or other tools talk to it), **comparison** with the tool the team uses today (what each does, what is still tied to the old one). Add facets only when there is something to say.
- Every page has the footer pointing to the map; the index lists the map and each page; the map is linked from another map.
- One diary note records what was created, linking the map.

## Dates and history

Every root page starts with two UTC dates so an agent knows its age without opening git:

```
---
created: 2026-10-26
updated: 2026-10-29
---
# Title
```

- **Nobody types the dates:** `scripts/dates.sh` writes the missing ones (from the page's first and last commit) and sets `updated` to today on pages whose text changed since the last commit, frontmatter not counted. Running it again changes nothing. Run it before committing.
- **The History section** at the end of the page (before the footer) keeps the changes that matter, one per line, newest first: `- 2026-10-29: rule X left, because Y (PR #160)`. It records what changes what the page claims (a decision, a new rule, a corrected number), not typos. Keep about 10 lines; the rest is in `git log`. The diary stays the wiki-wide record; History is the page's.
- **Why inside the page, not in a separate CHANGELOG:** the agent reads the whole page at once and never opens a separate file. Frontmatter sits in the first three lines, which a `head` or `rg '^updated'` finds.
- The diary and folders (`resources/`) carry no dates: the note has its time in its name.

## Linking

- Link in the body, the **first time** a subject of the wiki appears in each section; do not repeat the link in the same section. The footer is "see also", not the only place of links.
- For a part of a page use GitHub's heading anchor: lowercase, punctuation removed, space becomes hyphen (`[linear](linear.md#who-speaks-in-linear)`). Renaming a heading breaks the anchor; the lint warns.
- Relative links (`name.md`, `../src/x.ts`), which GitHub and Obsidian understand. Outside the wiki the link leaves the folder: `../docs/x.md`, or `../../...` from inside the diary.
- A link used as an example in text goes inside backticks so the lint does not read it.

## HTML pages: `resources/`

An interactive page (a graph, an animation) lives in `resources/<name>.html` and is linked like any page. The file is a fragment: it starts with `<meta charset="utf-8">` and `<title>`, with no `<!doctype>`, `<html>` or `<body>`, so the same page can also be published as an artifact. Libraries come from a CDN with an exact version. A browser only opens it over http(s), so serve the folder locally to view it.

## Commit what you wrote

Whoever writes in the wiki commits it in the same session, without waiting to be asked: the note, the page, the day index, and the files elsewhere the note describes. First run `scripts/dates.sh`, `scripts/day-index.sh` and `scripts/lint.py`. Commit only your own files, by path (`git add <file>`, never `git add -A`): what another session left modified in the checkout stays out. Committing is not publishing: pushing and opening a PR is the user's decision. `scripts/sync.sh` does the commit (after a lint), and the push when asked, safely when the checkout is behind or shared; for the index or inbox, which other sessions may also have edited, start with `sync.sh -W` and edit in the worktree it prints ([SKILL.md](../SKILL.md)).

## "Wiki update"

When the user says "wiki update" in a repo whose wiki says to confirm first: before editing, show a summary and wait for the ok. 1) **What changes:** one line per page, with the file and what comes in or out. 2) **New diary notes:** only the titles. 3) Ask "Apply?". Edit only after the yes. Without that rule in the wiki, or without the request, the note is written as usual.

## The lint

`python3 -I scripts/lint.py` checks:

- broken links and anchors, including those leaving the wiki;
- pages missing from the index, with no footer, empty, or orphan (no other page points to them);
- in the diary: each day index equal to the generated one, each note's name and heading, the day's link in the inbox;
- a note in the old format inside the inbox;
- each root page's dates (`created`/`updated` valid, `updated` not before `created`) and the History format (one dated line each, newest first, none newer than `updated`).

It prints `file:line: type: message`, exits 2 with problems and 0 clean. Pages ignored by git (personal data that exists only on one machine) are skipped; nobody links them, find them with `rg`. The lint does not catch contradictions between pages or stale claims.

## Shared checkouts

Several agents and people touch the same repo at once. Before editing, `git fetch` and fast-forward `<main>` if possible; if another session is in the main checkout, work in a new worktree from `origin/<main>` (`scripts/sync.sh -W`). The day index is generated: never merge or carry it, regenerate it where you commit. Diary and inbox are append-only, so a conflict there is solved by keeping both sides. Never push to the main branch without being asked, never force, never reset or clean work that is not yours.
