# Postmortem: <short title>

Blameless: causes are in the system, not in people or the agent. Cite events as `seq/time subject`.

- **Reported:** <who, when, what they saw>
- **Anchor:** card `<id>` · turn `<turn_id>` · trace `<trace_id>` · window `<since> – <until>`
- **Severity / impact:** <what was affected, how much>

## What happened (chain)

| # | Link | Event (seq · time · subject) | Evidence |
|---|---|---|---|
| 1 | Request | | what was asked, verbatim |
| 2 | Read | | what the agent looked at |
| 3 | Tool calls | | tool + key args |
| 4 | Decision | `decision.made` | choice + why |
| 5 | Effect | | what changed in the world |

Gaps found (missing events, unread context): <list or "none">

## Why

The reasoning at the decision, and why it was reasonable given what the agent had read.

## Contributing causes

- <cause 1: e.g. ambiguous request>
- <cause 2: e.g. no rule covering this case>
- <cause 3: e.g. tool default too broad>

## What changes

| Change | Where (file path) | Done |
|---|---|---|
| <rule or skill patch, one line> | `<wiki page or skill>` | commit `<sha>` |

Instrumentation to add (if events were missing): <subject / field>

## What went well

<detection, fast recovery, events that made this possible>
