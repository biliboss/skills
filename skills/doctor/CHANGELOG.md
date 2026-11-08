# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-11-08

### Fixed

- `--gate` failed every project doctor that follows the contract: the generic doctor did not ask for the `ok` findings.
  It now calls the project doctor with `--verbose`, and again without it when the flag is refused.

## [0.2.0] - 2026-11-08

### Changed

- Behaviour is proven by smokes and critical rules in the project doctor; the generic doctor no longer looks for tests.
  Without a verified `behavior` finding, the check `behavior smoke` is `warn`.

### Added

- `--gate`: no verified `behavior` finding is a `fail` (exit 1).

### Removed

- `--run-tests`.

## [0.1.1] - 2026-11-06

### Changed

- Pitfalls: the known drift is the acceptance test, one exit-code scale, a finding found while listing is still a finding.

## [0.1.0] - 2026-11-06

### Added

- The doctor protocol: five dimensions, findings `{dimension, check, status, evidence, action}`, text and `--json`
  output, exit codes 0/1/2, read-only by default.
- `scripts/doctor.py`: generic doctor (uv, stdlib only) for any repo; discovers and merges the project's own doctor
  (`just doctor`, `scripts/doctor*`, `<cli> doctor`).
- `scripts/test.sh`: 14 checks on a healthy and a broken temp repo.
