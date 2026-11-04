# Changelog

All notable changes to the interview skill are recorded here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-04

First version in the public plugin, adapted from a local copy of `pi-interview` 0.14.0 (see `ATTRIBUTION.md`).

### Added
- One window for every form: the first call starts a queue server on a fixed port (8398 by default) and opens one window; later calls enqueue their form on it, without a new window, and wait for their own answer. The page shows the form of the moment and how many wait, and moves to the next on its own after each submit. A closed window is reopened (once) by the next call.
- Drafts are saved on every change, on the server, to a recovery file (`~/.pi/interview-recovery/*.draft.json`). A closed window or a stale heartbeat no longer cancels the form.
- A form that times out stays answerable in the window. The waiting process exits 3 with what was marked and the recovery file path; an answer given later is written to that file.
- Passing a recovery file to `interview.ts` reopens the form pre-filled.
- The queue server exits by itself after 30 minutes with no forms. `test/run.sh` covers the queue, the timeout and the idle exit.

### Changed
- The default timeout is 1800 seconds (was 600), counted from when the form is on screen and reset by each change.
- Two processes racing to start the server are safe: the loser gets `EADDRINUSE` and uses the winner.
- Glimpse windows are opened by the queue server, so they outlive any single form.
