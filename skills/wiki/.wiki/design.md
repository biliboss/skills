# Design decisions

Why wiki-smith is shaped the way it is. Add a section when a decision changes; edit the old one in place and say what replaced it.

## One skill, smart routing (0.1.0)

Recording a daily note, fixing a topic page and building a map of content are one judgement made at the end of a session: what was this session worth to the next agent? One skill with a routing table avoids three skills that each fire alone and leave the other two undone. The detail of each route sits in [method.md](../references/method.md), so SKILL.md stays short.

## The diary is what happened, the page is what holds (0.1.0)

A lesson that lives only in a dated note is lost, because nobody searches the diary for rules. Every note that carries a lasting rule also changes the topic page, written as it holds now. This is the ingest step of [Karpathy's LLM wiki](../ATTRIBUTION.md), applied with a diary as the raw layer.

## One note per file (0.1.0)

Several agents write the same day, each on a branch. A note per file means they never edit the same file, and the day index is generated, so the only conflict left is solved by regenerating it.

## Scripts: POSIX sh plus one Python file (0.1.0)

The method started as three TypeScript scripts that need Node 22.6 or newer, which many machines do not have. Plumbing (note, day index, dates, sync) is `sh`, which runs on macOS BSD tools and GNU/Linux with nothing installed; the lint has real parsing (anchors with accents, code spans), so it is one stdlib-only Python 3 file, run with `python3 -I` so a stray module in the current directory is not imported.

## Config file, not forks (0.1.0)

Names and language differ per repo (`journal/` versus a Portuguese `diario/`, `Map:` versus `Mapa:`). A sh-sourceable `.wiki/wiki.config` that the scripts and the lint both read means one skill serves every repo. `WIKI_LANG=pt-BR` reproduces the original tool's output, type names included, which is how parity was tested.

## `day-index.sh` does not migrate old-format notes (0.1.0)

The original also moved hand-written notes out of a day file into their own files (with link rewriting that skips code). That was a transition aid for old branches. In `sh` it would need a markdown-aware rewriter, so it is an error with `file:line` instead, and the fix is `note.sh`. Revisit if a repo still has old-format days.

## `sync.sh` uses a worktree when the checkout is shared (0.1.0)

Agents and people share checkouts. When the checkout is behind, on another branch or has other people's changes, `sync.sh` carries only the given paths into a fresh worktree from `origin/<main>` (`git apply --3way`), commits, rebases and pushes there, then restores those paths in the checkout and fast-forwards it. A conflict stops with the checkout untouched. Pushing only happens with `-p`.

## `sync.sh` lints, never carries the day index, and has `-W` (0.1.1)

A carry takes the whole `git diff` of a path, so in a checkout shared by several sessions it also ships their uncommitted lines. The generated day index is therefore excluded from the carry and regenerated in the worktree (it lists only notes that are there). Hand-edited shared files (index, inbox) cannot be split into "my hunks" by a script, so the rule is: lint what will be committed and stop on red (a link to a page that was not carried is the usual sign), and offer `sync.sh -W` (a fresh worktree from `origin/<main>`, edited directly, committed from inside) as the way to touch them. Restoring paths in the checkout after a push never discards an edit that is not upstream; a failed fast-forward after a successful push is a message, exit 0. `note.sh` reads stdin only with `-b`, because agent shells leave stdin open forever.
