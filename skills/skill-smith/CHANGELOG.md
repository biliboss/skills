# Changelog

All notable changes to skill-smith are recorded here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.4.2] - 2026-11-06

### Changed

- Check the base before the release commit; `scripts/resolve_release_conflicts.py`.

## [0.4.1] - 2026-11-06

### Changed

- A workflow skill may take the practice's own short name from the literature (`backbrief`, `retro`) instead of `<entity>-<action>`.

## [0.4.0] - 2026-11-06

### Added
- Every skill has its own `README.md` and `CHANGELOG.md`: step 3 says what each holds (SKILL.md = the agent's rules, README = the human page that points to it, CHANGELOG = the history), step 4 creates the README when an updated skill lacks one, and step 6's lint checks both files and that the CHANGELOG's top entry matches `metadata.version`.
- `README.md` for skill-smith itself.

## [0.3.1] - 2026-11-06

### Changed

- Step 3: the `.sh` is the interface every harness calls; heavier logic lives behind it in a `uv` PEP 723 script or `jq`.

## [0.3.0] - 2026-11-06

### Added

- Step 1b: research the open source first (Hermes, GitHub, the literature's name) before CREATE, ADAPT or a
  MINOR+ UPDATE; findings in `references/prior-art.md`.

## [0.2.0] - 2026-11-03

### Added
- Step 6: install the skill where it runs (plugin update, pi links, reload in open sessions).

### Changed
- Frontmatter: description under 1024 characters and without a bare `: `, which pi rejects.

## [0.1.1] - 2026-11-03

### Added

- Rule: a skill's actions are `.sh` scripts in `scripts/`, not an MCP server, unless they need a long-lived connection or state.

## [Unreleased]

## [0.1.0] - 2026-11-03

### Added

- First release: three modes, CREATE, UPDATE and ADAPT, plus a "just Edit it" path for one-line fixes ([SKILL.md](SKILL.md)).
- The worth-it gate ([from skillify](https://github.com/Yeachan-Heo/oh-my-claudecode/blob/0564555b63dfedd158669c6799d53743abd7d6bf/skills/skillify/SKILL.md)) and the do-not-capture list ([from Hermes](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L422-L446)).
- The "patch before you create" order and the content rules ([from Hermes](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py#L390-L497)).
- UPDATE with cross-skill propagation, per-file diffs and semver ([from skillify-pro](https://github.com/coreyhaines31/makerskills/blob/ea7dd78515839ff11fc24e79ba0c53db2d5fff6c/skills/skillify/SKILL.md#mode-update)).
- ADAPT with the license gate and three buckets ([references/adapt.md](references/adapt.md)).
- A CHANGELOG and `metadata.version: 0.1.0` for every skill it creates.
- Its own memory in [.wiki/](.wiki/README.md): lessons about running itself, and the design decisions.
- A README with install instructions ([README.md](README.md)).
- MIT license ([LICENSE](LICENSE)) and upstream credits ([ATTRIBUTION.md](ATTRIBUTION.md)).

[Unreleased]: https://github.com/biliboss/skill-smith/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/biliboss/skill-smith/releases/tag/v0.1.0
