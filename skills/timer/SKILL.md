---
name: timer
description: >-
  Run a countdown timer in the Mac menu bar, driven by the agent. The agent sets, pauses, resumes, extends and stops the timer through scripts/timer.sh; the StatusTimer app only displays it (a timer icon plus MM:SS in the macOS menu bar clock look, a sound and a notification at zero). Use when the user says "start a timer", "timer de 25 minutos", "cronômetro na barra", "pause the timer", "retoma o timer", "mais 5 minutos no timer", "para o timer", "quanto falta", "how much time is left", "instala o timer". Not a reminder or calendar event (no Google Calendar, no cron): this one is a visible countdown on this Mac.
metadata:
  version: 0.2.0
---

# timer: a countdown in the menu bar, set by the agent

The app has no buttons and no menu. It is only the widget view; **the engine is you**. You write the timer through `scripts/timer.sh`, the app watches the state file and draws it. `S` below is this skill's `scripts/`.

State lives in `~/.local/state/status-timer/state.json` (`status` idle|running|paused, `ends_at`, `remaining`, `label`, `updated_at`). Only `timer.sh` writes it.

## Steps

1. **Is the app there?** If the user sees no timer in the menu bar, run `S/timer.sh install` (builds the app with `swift`, copies it to `~/Applications/StatusTimer.app`, opens it). It is idempotent: it quits a running copy first. The timer works without the app (state and `status` still work); only the display needs it.
2. **Start:** `S/timer.sh start <dur> [label]`, for example `start 25m "foco"`. `<dur>` is `25` (minutes), `25m`, `90s`, `1h` or `1:30` (mm:ss). Starting again replaces the current timer.
3. **Pause / resume:** `S/timer.sh pause`, `S/timer.sh resume`.
4. **Add time:** `S/timer.sh add 5m` (running or paused timer).
5. **Stop:** `S/timer.sh stop` (back to idle, the bar shows only the timer icon).
6. **How long is left?** `S/timer.sh status` prints `MM:SS label`, `paused MM:SS label` or `idle`. Use it to answer "quanto falta" instead of computing by hand.
7. **Quit the app:** `S/timer.sh quit` (it does not touch the state).

## What the bar shows

The icon is a Nerd Font timer glyph (`IosevkaTerm Nerd Font`, falling back to the SF Symbol `timer`); the time uses the menu bar clock font with monospaced digits and the label colour.

- idle: icon only.
- running: icon + `MM:SS` (`H:MM:SS` above one hour).
- paused: icon + `MM:SS` in the secondary label colour.
- finished: icon + `00:00`, until the next state change.

The label is not in the bar; it shows as the tooltip when the pointer rests on the item.

At zero the app plays Glass, posts "Tempo esgotado" with the label and keeps showing `00:00` until the next state change. Nothing is written back.

## Rules and why

- **Never edit `state.json` by hand and never write it from another script.** One writer per field keeps the display and the script from disagreeing; the script writes atomically (temp file, then `mv`), and a hand edit can leave half a JSON.
- **Do not add controls to the app.** The owner decided the app is display only; every action goes through the agent so it can also be logged and chained to other work.
- **Pass a label when the timer has a purpose.** The label shows in the tooltip and in the notification, so the user knows what ended.
- **Do not run `install` just to start a timer.** It rebuilds and relaunches the app; use it only when the app is missing or the app code changed.
- **Bad input exits non-zero with a message** (`bad duration`, `nothing running to pause`). Read the message and fix the call; do not retry the same command.
- **NATS is best effort.** If the `nats` CLI exists and `127.0.0.1:4222` answers, each verb publishes `mesa.timer.<verb>` with the state JSON (1 s timeout). A down broker never fails the command.

## Tests

- `STATUS_TIMER_STATE_DIR=<tmp>` points the script (and the app) at another state directory; `STATUS_TIMER_NOW=<epoch>` fixes the clock. Use both to test without touching the real timer.
- App library: `cd app && swift build && swift test` (`TimerCore`: state decoding, remaining, formatting, duration parsing).
