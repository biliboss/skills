---
name: doctor-driven
description: >-
  Build a capability by writing an executable .doctor.yaml contract before its implementation,
  observing a real failure, then correcting it and proving the user's journey. Use for doctor-driven development.
metadata:
  version: 0.1.0
---

# Doctor-driven development

Load the sibling [doctor skill](../doctor/SKILL.md) and its [contract reference](../doctor/references/contracts.md).
Before implementation, write or extend the nearest app/library `.doctor.yaml`: intent, capabilities, checks,
keep and success. Each check declares its expected behavior, the meaningful red reason and the remedy.
Preserve existing invariants in keep. Use explicit fast, runtime and journey kinds.
A capability used by a person or another real system requires a journey check; file presence alone does not prove use.

Run the new check against the unchanged behavior with `doctor --record-red ID` (select its kind if necessary).
Review the observed output: confirm it corresponds to the declared reason, not missing infrastructure, an inverted
assertion or an intentional unconditional failure. Record that review with `--confirm-red` and `--confirm-observed`.
Do not alter the assertion to manufacture red. Use a fixture representing an actual unavailable capability when
production state must remain untouched. Clearly identify fixture evidence as fixture evidence.

Implement the smallest correction. Run fast checks while editing, then runtime and the actual journey.
Run `doctor --all` on the capability before delivery. PASS requires confirmed red evidence tied to the check and
referenced scripts. Changed definitions invalidate prior evidence. A partial selection does not fully validate a capability.
If a required adapter or environment is unavailable, report PEND and the missing prerequisite; do not claim success.

Report the contract path, observed red, correction, green evidence and anything not exercised. Keep private output
in the user's state directory, never in the public repository. Do not replace existing CI gates without authorization.
