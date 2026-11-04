# Changelog

All notable changes to wiki-smith are recorded here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] - 2026-11-04

### Added

- Routing row "A public skill was installed or studied" and the section "Absorbing a public skill": vet it (text only, no script, key, paid service or data sent out), read it whole, ingest only the new into the topic's map with its origin, record the install id and when to load it, and prefer the public skill over an own one unless the knowledge is the house's.

## [0.1.2] - 2026-11-03

### Changed

- The description tells agents to load wiki-smith before writing anything in `.wiki/`, for any wiki request (creating a page or doc too), and adds the triggers "wiki", "create a doc in .wiki" and "cria um doc no .wiki".
- The "Shared files across sessions" pitfall now says how to commit only your own lines of a shared `index.md`, inbox or day index (a blob from `HEAD` plus your lines, `git update-index --cacheinfo`, a direct commit) instead of only warning that the carry takes the whole diff.

## [0.1.1] - 2026-11-03

### Fixed

- `note.sh` no longer hangs in agent shells and CI. It used to read stdin whenever it was not a TTY, and there stdin is open but never closes. It now reads stdin only with the new `-b` flag.
- `note.sh` leaves exactly one blank line between the title and the body (a later `cat >>` used to produce two); without `-b` the file ends right after the title line, so a paragraph appended with `>>` starts with its own blank line.
- `sync.sh` no longer ships another session's uncommitted lines in the generated day index: the day index is excluded from the carried diff and regenerated in the worktree with `day-index.sh`, so it lists only notes that are in the commit.
- `sync.sh` never discards a local edit that is not upstream when it restores paths after a push (a shared file that differs from what was pushed is kept), and removes only the untracked files it carried.
- When the checkout cannot be fast-forwarded after a successful push (local `<main>` diverged, or overlapping edits), `sync.sh` says why and exits 0 instead of implying a failure.

### Changed

- **Behaviour change:** a body piped into `note.sh` is now ignored unless `-b` is given (`printf '%s\n' "text" | note.sh -b "Title"`).
- `sync.sh` runs `lint.py` on exactly what it will commit, in every mode, and refuses a red lint (exit 1, checkout untouched, carry worktree removed). It also lints again after the rebase, before the push.
- Paths are resolved physically (`pwd -P`), so a symlinked temp directory such as macOS `/var` no longer reads as "outside the repository".

### Added

- `sync.sh -W`: prints a fresh worktree from `origin/<main>` to edit shared files (index, inbox) in; `sync.sh -m ... [-p] PATH...` run from inside it commits there, and with `-p` rebases, pushes, fast-forwards the main checkout where it can and removes the worktree.

## [0.1.0] - 2026-11-03

### Added

- First release: one skill that routes a session to a daily note, a topic-page fix, a map of content with facet pages, or nothing ([SKILL.md](SKILL.md)).
- The full method in English ([references/method.md](references/method.md)) and a per-repo config, `.wiki/wiki.config` ([references/config.md](references/config.md)).
- POSIX `sh` scripts: `note.sh`, `day-index.sh`, `dates.sh`, `sync.sh`; and a stdlib-only `lint.py` with `en` and `pt-BR` output.
- Templates for a page, a map and a note, an example config and a pt-BR preset ([templates/](templates/)).
- Its own memory in [.wiki/](.wiki/README.md), a README, the MIT license ([LICENSE](LICENSE)) and credits ([ATTRIBUTION.md](ATTRIBUTION.md)).

[Unreleased]: https://github.com/biliboss/wiki-smith/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/biliboss/wiki-smith/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/biliboss/wiki-smith/releases/tag/v0.1.0
