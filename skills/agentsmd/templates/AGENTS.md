# <Project>

<One sentence: what this is and who it serves. Only what the code does not say.>

Read `STATE.md` before any task that depends on current status. Its claims age; check their dates.

## Commands

- Install: `<command>`
- Test: `<command>`
- Check before commit: `<command>`
- Change in `<path>` → `<smallest command that proves it>`

## Boundaries

- Always: <rule> because <reason>.
- Ask first: <action only the owner decides>.
- Never: <rule> because <reason>.

## Where things live

- Source of truth for tasks: <tracker URL>
- Default branch and how work lands: <main directly | branch and PR>
- Canonical docs: <path or URL, one line on when to read it>
- Secrets: <vault and variable names, never values>

## Pitfalls

- <Thing that looks wrong or fails>: <exact sequence that avoids it>.

## When something fails

- <Environment or gate that can break>: stop and report which call failed. Do not work around it silently.
