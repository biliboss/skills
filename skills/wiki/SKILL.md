---
name: wiki
description: >-
  Keep a project's wiki in the central checkout `$WIKI_HOME/<projeto>/` (one folder per project),
  used from any folder: the memory agents read and maintain themselves. At the end of a session
  it looks at what happened and routes: a daily note, a fix to a topic page, a new map of content
  with its facet pages, or "nothing worth recording". Then it fixes the dates, regenerates the day
  index, lints, commits only its own files and syncs. Also looks things up (rg inside
  `$WIKI_HOME/<projeto>` first). Load it BEFORE writing anything in the wiki, for any request
  that touches it, never by hand-editing first. Use when the user says "wiki", "update the wiki",
  "anota no wiki", "cria uma página na wiki", "consulta o wiki", "lint the wiki", "create a moc
  for X". Not skill-smith: that writes skills (SKILL.md), this writes wiki pages. A new project is
  a new folder under `$WIKI_HOME` with its `wiki.config` (`REPO=owner/name`), created from
  `templates/`; a few repos keep a local `.wiki`, operated with `-w <repo>/.wiki`.
metadata:
  version: 0.3.0
  license: MIT
---

# wiki — keep the project's wiki in `$WIKI_HOME`

A wiki is the project's memory, written for agents: they find the rule here instead of asking again. The diary holds what **happened**; the topic page holds what **holds now**. A lesson that lives only in the diary is lost. This skill decides which of the two a session needs, writes it the way this wiki's own rules say, and checks it. The wiki lives in one central checkout — `$WIKI_HOME` (default `~/wiki`, the `biliboss/wiki` repo), one folder per project: `$WIKI_HOME/<projeto>/` — so it works from any folder.

Full method (file types, note format, ingest, linking, dates, commit): [references/method.md](references/method.md). Config keys: [references/config.md](references/config.md). Credits: [ATTRIBUTION.md](ATTRIBUTION.md). Changes: [CHANGELOG.md](CHANGELOG.md). Its own memory: [.wiki/](.wiki/).

`<skill>` below is this skill's folder. Every script takes `-w <wiki dir>`, `-P <project>` and `-c <config>` (default `<wiki>/wiki.config`); in `sync.sh`, `-p` still means push and `-P` is the project. Without `-w`, the wiki folder resolves in this order: `$WIKI_DIR`; `-P`/`$WIKI_PROJECT` → `$WIKI_HOME/<project>` (an error if it is missing); the `$WIKI_HOME` project whose `wiki.config` has `REPO=` equal to the current repo's `origin`; then `$WIKI_HOME/biliboss`.

The machine values — `WIKI_HOME` (default `~/wiki`), `WIKI_REPO` (default `biliboss/wiki`) and `WIKI_REMOTE` — live in `.env` beside this SKILL.md (see [example.env](example.env)); `$WIKI_SKILL_ENV` overrides that path, and the environment wins over the file. When the wiki is not pinned with `-w`/`$WIKI_DIR`, the scripts maintain the checkout: they clone `$WIKI_REMOTE` when `$WIKI_HOME` is missing or empty and `git pull --ff-only` when it holds `.git` (a failed pull warns once and the work goes on with the local copy); they never stash, reset or clean. A few repos keep a local `.wiki/` at the root instead: work it with `-w <repo>/.wiki`.

## Step 0 — Find the wiki and its rules

1. The wiki is `$WIKI_HOME/<projeto>/`; the scripts resolve the project by the order above (`-P` pins it, and a repo resolves to the project whose `wiki.config` has its `origin` in `REPO=`). If the repo has no project of its own, say so and offer to create one: a new folder under `$WIKI_HOME` with its `wiki.config` (`REPO=owner/name`), from [templates/](templates/) (`wiki.config.example` first); never create it unasked. A few repos keep a local `.wiki/` at the root — same method, `-w <repo>/.wiki`.
2. Read `$WIKI_HOME/<projeto>/wiki.config` if present (names: diary folder, inbox, index, footer label, date keys, main branch). Without it the defaults are generic English: `journal/`, `inbox.md`, `index.md`, `Map:`, `## History`, `created`/`updated`.
3. **The wiki's own rules win.** If the project has a page on how to maintain it (`rg -n -i 'maintain|manter' "$WIKI_HOME/<projeto>" -l`) or an `AGENTS.md` rule about the wiki, read that section and follow it where it differs from this skill.
4. If the user asked for "wiki update" and the wiki (usually the index) says to **confirm first**, do Step 1 and Step 2 as a plan only: one line per page with what changes, the titles of new notes, then ask "Apply?" and edit only after a yes. Otherwise act.

## Step 1 — Look at what happened, then route

Read the session (and `git diff`, `git log` for the work done). Pick **every** row that applies, and nothing else:

| What the session had | What to do |
|---|---|
| A decision, delivery, change of course, incident or research | A daily note: `scripts/note.sh -b "Title that says what changed"` with the paragraph piped in. Then the day's line in the inbox. |
| A rule, lesson or fact that holds beyond today | Also fix the **topic page**: the rule as it holds now, no history (history stays in the note and in the page's History section). Correct what the page said before; never stack "it used to be". |
| A new subject with several facets (it will come back, and one page would mix kinds) | A map of content `moc-<topic>.md` plus pages `<topic>-<facet>.md` (cheatsheet, install, integration, comparison with the current tool...). See "New subject" below. |
| A public skill was installed or studied | **Absorb it**: only what is new goes into the topic's map, with its origin, plus the install id and when to load it. See "Absorbing a public skill" below. |
| Nothing worth recording (only intermediate steps, or what a commit already says) | Say so in one line and create nothing. Padding the diary makes it unreadable. |
| The code changed shape and the map went stale (a module in the map's `modules` list has a commit after `last_mapped` — `lint.py` reports `stale-map`), or there is no code map yet | The **map mode**: create or update the code-map page. See "Code map" below. |

Only a fresh note is ever created for the diary; never rewrite another agent's note.

## Step 2 — Write

**Daily note.** `scripts/note.sh "<title>"` creates `<DIARY_DIR>/<today>/<HHMM>-<slug>.md` in UTC and prints the path (slug rules and `-2` on collision are in the script). **Stdin is read only with `-b`**: agent shells and CI leave stdin open forever, so without `-b` the script never waits for it. Pipe the body: `printf '%s\n' "<paragraph>" | scripts/note.sh -b "<title>"`; `-b` puts exactly one blank line between the title and the body. Without `-b` the file is just the title line; to add the paragraph afterwards start it with a blank line: `printf '\n%s\n' "<paragraph>" >> "$path"`. The body is one well-written paragraph: what happened, why it matters, where the evidence is (commit, PR, issue), with a link to the topic page. Links are relative to the day folder (`../../page.md`). Template: [templates/note.md](templates/note.md).

**First note of the day:** `scripts/day-index.sh` creates the day's index; then add the day at the top of "last days" in the inbox. If the note changes how the repo works, also add one line to the inbox's highlights. The inbox never holds a note.

**Topic page (ingest).** Find it (`rg -n -i '<word>' "$WIKI_HOME/<projeto>"`); if it does not exist and the subject will return, create it (template: [templates/page.md](templates/page.md)); if it is small, put it in a section of a nearby page. Write the rule as it holds now. If a change alters what the page claims, add one line at the top of its History section. The note links to the page.

**New subject.**
1. Write the pages first, one facet each, each self-contained from the first sentence. Typical facets: **cheatsheet** (the one to start with: addresses, commands, shortcuts), **install**, **integration**, **comparison with the tool in use today**.
2. Create `moc-<topic>.md` ([templates/moc.md](templates/moc.md)): an opening paragraph, "the pages" (one line each, cheatsheet first), "what to know first" (the few rules that bite).
3. Give every page the footer (`Map: [moc-<topic>](moc-<topic>.md) · Related: ...`), add the map and each page to the index, and link the map from at least one other map.
4. A note in the diary says what was created and links the map.

## Step 3 — Close (always, in this order)

1. `scripts/dates.sh` — the `created`/`updated` frontmatter, from git. Idempotent.
2. `scripts/day-index.sh` — regenerate the day index. Never edit it by hand.
3. `python3 -I scripts/lint.py` — fix every `file:line: type: message` it prints until it exits 0 (exit 2 means problems). Do not ship a red lint.
4. Commit **only your own files, by path**, never `git add -A`: `scripts/sync.sh -P <projeto> -m "wiki: <what>" <path>...`. It commits in place when the checkout is on `<main>`, current and has no changes outside your paths; otherwise it carries your paths into a fresh `git worktree` from `origin/<main>`. Either way it lints exactly what it commits and refuses a red lint (exit 1, checkout untouched, carry worktree removed). In the carry the generated day index is never copied: it is regenerated in the worktree, so it lists only the notes that are in the commit. Add the attribution lines the repo or your host requires to the message.
5. **Push only when the user asked to sync:** the same call with `-p` (fetch, rebase, `push HEAD:<main>`, fast-forward the checkout, remove the worktree). Never force, never touch other people's modified files: a file that differs from what you pushed and may hold another session's edits (index, inbox) is left as it is. If the checkout cannot be fast-forwarded (local `<main>` diverged, or overlapping local edits) it says so and still exits 0, because the push worked. Open a PR only when asked.

Commit what you wrote in the same session without waiting to be asked; publishing is the user's call.

## Code map

The map mode keeps one page that is the blueprint of the code — what each top-level folder does, the flows, the pitfalls — so a fresh session reads the map instead of re-deriving it. The method comes from kingbootoshi's Cartographer (MIT), adapted by Luiz Ribeiro Coelho in viacorretor/the-viacorretor#143; `scripts/map.py` is derived from his `mapear.py` (see [ATTRIBUTION.md](ATTRIBUTION.md)).

**Create.**

1. Measure the repo: `python3 -I scripts/map.py <repo>` (or `--format json`). It lists only git-tracked files — the map does not depend on the checkout — and estimates tokens as bytes/4 per top-level folder.
2. Split the folders into groups of up to ~120k tokens each (use `por_pasta`; a folder over the budget is its own group).
3. Send one Explore subagent per group, all in a single message. Each returns its module section: what it does, key files, entry points, who it talks to.
4. Write the page from [templates/code-map.md](templates/code-map.md) — `mapa-do-codigo.md` in a pt-BR wiki, `code-map.md` otherwise. Fill the frontmatter: `last_mapped` = today, `total_arquivos` and `total_tokens` from the script, `modules` = the top-level folders the page covers (the list `--check` watches). Merge the groups' sections into Módulos and write the mermaid diagrams from what they report.

**Update.**

1. `python3 -I scripts/map.py --check <página> [--repo <repo>]` lists the stale modules, one per line (exit 2), or exits 0 when the map is current. `--repo` defaults to the page's folder and any folder inside the code repo resolves to its root — a `.wiki/` inside the repo needs no flag; a central wiki in `$WIKI_HOME` does, and each module it cannot reach is reported `não conferido (use --repo)` instead of passing as fresh.
2. Remap only the stale modules — one Explore subagent each — and rewrite only their sections in Módulos, plus any flow or pitfall they invalidate.
3. Renew `last_mapped`, `total_arquivos` and `total_tokens` from a fresh `map.py` run.

**Rule:** names of things only — variables, functions, files. Never values, secrets or personal data; reference where a secret lives instead.

## Absorbing a public skill

When a public skill covers the subject, do not write a house skill for it: use the public one and let the wiki hold what is ours.

1. **Find and vet before installing:** search the catalog (official over well-known community); it must be text only, with no script, API key, paid service or data sent out (nothing to a vendor's telemetry). Read the code of any plugin first. Install only with the owner's OK and note the catalog id.
2. **Read it whole and sort it:** what fits this case × what does not (one line on why); evidence (official source, study) × practitioner heuristic, marked as such.
3. **Ingest only the new** into the topic's map or page, with the origin (the skill plus the source it cites, linked). Never copy the whole skill.
4. **Record in the map:** which public skills exist, the id to install on another profile or machine, and when to load each.
5. **Own skill or public?** Own only when the knowledge is ours (house procedure, voice, internal tool); fast-changing public knowledge stays in the public skill. A house skill points to the public one and to the wiki, without duplicating either.

## Consulting the wiki

`rg -n -i '<keyword>' "$WIKI_HOME/<projeto>"` (or skim the index), then read **only** the matching page or section, never the whole wiki. **Check the checkout first** (`git -C "$WIKI_HOME" status -sb`): a checkout behind `origin/<main>` can lack the pages you want, so read them with `git -C "$WIKI_HOME" show origin/<main>:<projeto>/<page>.md` (list with `git -C "$WIKI_HOME" ls-tree -r --name-only origin/<main> <projeto>`) instead of concluding they do not exist; do not pull over another session's local changes just to read. For what happened: the inbox (short), then only the days that matter; one day = its index and the notes it lists. If the repo has specs, they say what the system promises: `rg -n -i '<keyword>' <specs dir>`.

## Pitfalls

- **The diary is not the page.** A rule written only in a note is lost; ingest it into the topic page in the same session.
- **Rules without history.** "Before creating a card, search for existing ones", not "we used to duplicate cards". The story stays in the note.
- **One note per file.** Several agents write the same day; they must never edit the same file. The day index is generated; conflicts there are solved by running `day-index.sh` again.
- **Shared files across sessions.** The day index, `index.md` and the inbox hold every session's uncommitted edits in one checkout. `sync.sh` never carries the day index (it regenerates it in the worktree) and lints before committing, but it cannot tell which hunks of a hand-edited `index.md` or inbox are yours: the carry takes the whole diff. When `git diff` on one of them shows lines that are not yours, skip `sync.sh` and stage only your lines: write `git show HEAD:<file>` plus your lines to a scratch file, `git update-index --cacheinfo 100644,$(git hash-object -w <scratch>),<file>`, `git add` your own new files by path, lint, then `git commit` — the other session's lines stay in the working tree, uncommitted.
- **A topic page is shared too.** Another session may be editing the same page right now. `git pull` (or fetch) right before you edit a page, and commit right after. In a `sync.sh -W` worktree, apply only your diff (`git diff <file> | git -C <worktree> apply --3way`), never `cp` the whole file from the checkout: the copy erases what the other session already pushed.
- **Commit as the agent, not the owner.** Before the first commit in a repo, check `git config user.name`/`user.email` against the identity the repo's rules give agents (an AGENTS.md or a wiki page on GitHub identity). If it is the owner's, set it (the repo's config script, or `GIT_AUTHOR_*`/`GIT_COMMITTER_*`) first: a commit that is already pushed keeps the wrong author, because history on `<main>` is never rewritten.
- **A repo's own date script can touch pages you did not edit.** After running it (or `dates.sh`), `git status` and restore every page outside your change set (`git checkout -- <path>`) before committing, or the commit carries unrelated date churn.
- **The diary day is UTC.** A note written late in the local evening lands in tomorrow's folder, so it is that day's first note: run `day-index.sh` and add the day to the inbox's "last days", or the lint fails with the day missing from the inbox.
- **A red lint on `origin/<main>` blocks every sync.** `sync.sh` lints the whole commit tree, so a problem already pushed by someone else (a History out of order, a broken link) refuses your commit too. Fix that page (a small, mechanical fix) and pass its path to the same `sync.sh` call; do not wait for its author.
- **`note.sh` prints an absolute path.** When the topic page's History links the note, write it relative to the page (`diario/<day>/<HHMM>-<slug>.md` from the wiki root), never paste the printed path: the lint reads an absolute link as broken. Create the note first, then write the page's link from its file name.
- **A `sync.sh` without `-p` leaves a local `wiki-sync/*` branch.** If you then rerun with `-p`, delete your own leftover branch (`git branch -D wiki-sync/<stamp>`); never the ones from other sessions.
- **A new page needs an index line and the footer** (`Mapa: … · Relacionadas: …`) in the same commit; the lint fails without them.
- **Never wait on stdin.** `note.sh` reads the body only with `-b`; in an agent shell a bare read blocks forever. The same applies to any script you add.
- **A dictated conversation (speech-to-text of a meeting) becomes a topic page, not a transcript**: the rules and
  numbers as they hold, each estimate marked as such, and an "Em aberto" list for what the transcript garbled or left
  ambiguous, with your reading of it ("R$ 1.00" read as R$ 550 + R$ 1.100), never silently fixed. When he then gives
  the real figure or corrects a person's role (a PJ, not a partner), edit the page in place in the same session.
- **A checkout with other sessions' changes (or local commits ahead of origin) is never pulled or stashed by hand to
  publish a page**: a path-limited `git stash push` fails on a new untracked page, the pull aborts over their edits, and
  `gh-app` refuses a push that carries their non-wiki commits. Use `sync.sh` (it carries your paths into a worktree of
  `origin/<main>`); for a later edit of the same page, apply it in a fresh detached worktree of `origin/<main>`, push
  `HEAD:<main>`, and copy the result back to the checkout.
- **Do not record the transient**: a command that failed once and worked on retry, an environment glitch, a one-off task. Capture the working fix on the topic page, never "X is broken" (it hardens into a refusal after the cause is gone).
- **Links:** relative, first mention per section only; an anchor is GitHub's slug of the heading (lowercase, no punctuation, accents kept, space becomes hyphen). Renaming a heading breaks its anchors; the lint says so. Put a link example inside backticks so the lint does not read it.
- **Rename or delete a page:** `rg -l 'old-name' "$WIKI_HOME/<projeto>"` and fix every link, anchors included; delete only after the content moved.
- **Page size:** past about 150 lines, or when rule, procedure, reference and history mix, split by kind.
- **Private data stays out.** Wiki pages are committed; keep secrets, tokens and personal data out, and reference where the secret lives instead.
- **Lint limits:** it does not catch contradictions between pages or stale claims; that is an agent's review when time allows.
- **`day-index.sh` limit:** a day file with hand-written old-format notes is an error (file:line), not migrated; move each note into its own file with `note.sh`, rerun.

## Step 4 — Keep your own wiki

If this run taught something about running this skill itself (a routing mistake, a script quirk), add one line to [.wiki/lessons.md](.wiki/lessons.md): `- YYYY-MM-DD — <rule + why>`. Edit the source, `skills/wiki/` in the plugin repo ([biliboss/skills](https://github.com/biliboss/skills)), commit and push, then update the plugin (`claude plugin update biliboss-skills@biliboss`); never the installed copy in the plugin cache, which an update overwrites. Design decisions go in [.wiki/design.md](.wiki/design.md).
