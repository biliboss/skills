# Changelog

## 0.3.0

- `bots.py` guards registry writes (lock, atomic replace, exactly one principal) for the hire, roster, rebrief and fire skills.
- `ag-notify <listener> stop|notification`: the hook a listening bot plants in another bot's settings; finds the listener's live terminal, waits for an empty `❯` line (up to 10 min, detached from the hook) and `hc send`s a `<hook from="<target>">` line.
- `bots.py` merges and removes listener hooks in a bot's project settings (`add_listener`, `remove_listener`, `listeners`) for the listen and roster skills.

## 0.2.0

- Bots sidebar shows live state per bot (working, blocked, done).
- `bots.py list` keeps the principal first, then most recent session activity.
- Option+1-9 navigation for bots.

## 0.1.0

- Bots sidebar, local registry, explicit UUID sessions and dedicated workspaces hidden from Spaces.
- Idempotent personal layout installation and preservation of old bot folders before empty setup.
