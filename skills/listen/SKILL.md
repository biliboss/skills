---
name: listen
description: Use when an agent should be told in Herdr whenever another bot finishes a turn or needs someone. Triggers "listen", "escuta o bot", "me avisa quando o X terminar", "para de escutar o X". The listener registers hooks in the other bot's project settings; nothing is sent by hand. Not roster (lists) and not bili-agents' ag-open (opens a bot).
metadata:
  version: 0.1.0
  license: MIT
---

# listen

Listening means: when the target bot stops (`Stop`) or asks for someone (`Notification`), Claude Code runs
`ag-notify`, which types a `<hook from="<target>">...</hook>` line into the listener's live Herdr terminal, only
when that terminal's input line is empty. If the listener is not live, nothing is sent.

1. From the listener's folder, run `scripts/listen <target-id>`. The listener is the registered bot whose folder is
   the current directory; elsewhere, pass `--as <listener-id>`. `--events stop,notification` narrows the events.
2. The result is JSON on stdout (`target`, `listener`, `events`, `settings`, `needs_reload`), the refusal on stderr,
   exit 0 or 1. It edits `<target folder>/.claude/settings.json`, merging into `hooks.Stop` and `hooks.Notification`;
   other hooks and keys stay. Running it again changes nothing.
3. `needs_reload: true` means the target is live and a running Claude Code only loads new hooks after `/hooks` or a
   restart. Say so to the owner; never restart or type into the target's session to make it pick them up.
4. `scripts/listen <target-id> --off` removes only this listener's entries.

A bot cannot listen to itself. The hook line names the target, the event, the session and how to read the target's
tab (`hc read <address>`); answer it by reading that tab, not by guessing.

Details: [README](README.md), [CHANGELOG](CHANGELOG.md).
