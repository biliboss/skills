---
name: self-learning
description: >-
  Review how a named skill performed in real sessions and propose small, cited improvements. Use for
  "self-learning <skill>", "learn from skill usage", or "improve this skill from sessions". Unlike retro,
  this starts with one skill and requires proof that it was actually loaded.
metadata:
  version: 0.1.0
---

# Learn from actual skill use

1. Read the named skill and its references. Choose relevant session JSONL files; the scanner supports Claude Code
   transcripts. Other transcript formats need an explicit adapter and remain unverified.
2. Run `scripts/self-learning.sh scan <skill-name> <session.jsonl> [more sessions]`. It reuses the retro scanner
   for correction, marker and workaround signals, and pairs `Read` or `Skill` calls with successful results to
   establish actual loads. A mention, failed call or unpaired call is not a load.
3. Read the surrounding conversation for each candidate. A matched signal is a lead, not proof that the skill
   caused the failure. Drop environment failures, one-off requests, unresolved workarounds and unsupported
   inferences. Prefer one small edit to a passage already responsible for the decision. Do not add a rule
   already present elsewhere in the skill.
4. Create a proposal with `propose <SKILL.md> --session <file> --line <signal-line> --old '<exact passage>'
   --new '<replacement>' --output <local-state/proposal.json>`. Cite the session, the signal's line and quote,
   and the completed load's location. Explain the connection to the proposed edit. Proposals are private local
   artifacts: store them outside the repo in the user's state directory because transcripts can contain secrets.
5. Show the concrete diff and evidence. Apply only when the user explicitly accepts the proposal. Run
   `apply <proposal.json> -- <doctor-command> [args]` using the relevant full doctor command; a partial or empty
   check does not validate a skill change. The command runs in the skill directory. A nonzero exit, missing
   executable or timeout restores the exact original. A stale target or source rejects the proposal before editing.
   If the doctor itself changes SKILL.md, the script refuses to overwrite it; inspect that conflict before continuing.
6. Keep an accepted change only after the relevant doctor is green. Follow the plugin's existing version,
   changelog and PR process for the retained edit. Report the evidence, doctor result, and any unsupported harness.

The scanner does not generate rules autonomously. Drafting and judging the connection require reading context.
For a behavioral example and command usage, see [README.md](README.md).
