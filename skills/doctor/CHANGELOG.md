# Changelog

## [0.2.0] - 2026-11-08

### Added
- Separate YAML capability executor, evidence lifecycle, incremental selection and explicit adapters.

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

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
