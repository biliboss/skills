# Prior art

Read on 2026-11-09. One line per source: what it says and the idea taken.

## Format and tools

- [agents.md](https://agents.md): plain Markdown, no required fields, the closest file wins, chat overrides the file. Taken: free headings, nested files.
- [Claude Code memory](https://code.claude.com/docs/en/memory): target under 200 lines; imports do not reduce context cost; AGENTS.md is skipped when CLAUDE.md exists, so `CLAUDE.md` imports it; contradictory rules may be resolved arbitrarily. Taken: the size limit and the one-line `CLAUDE.md`.
- [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md): files concatenated from root to working directory; `project_doc_max_bytes` defaults to 32 KiB and later files are dropped past it. Taken: the audit limit across the chain.

## Evidence

Both are preprints with different setups, read from their abstract pages, not the full text. They disagree on cost; measure in your own repository before claiming a gain.

- [Gloaguen et al., arXiv 2602.11988](https://arxiv.org/abs/2602.11988): context files do not generally raise task success and raise inference cost; generic overviews do not help; non-standard practices do. Taken: no generic overview, only what the agent cannot infer.
- [Lulla et al., arXiv 2601.20404](https://arxiv.org/abs/2601.20404): reports lower runtime and output tokens with AGENTS.md, and comparable completion. Taken: a good file can pay for itself, so keep it small and specific.

## Real files

- [apache/airflow](https://github.com/apache/airflow/blob/HEAD/AGENTS.md): invariants with their reason; "stop and tell the user which call failed"; decisions in ADRs; generated command block.
- [vercel/next.js](https://github.com/vercel/next.js/blob/HEAD/AGENTS.md): a rule that declares its exit; change-to-command map. Its 538 lines also show the cost of growing.
- [supabase/pg-toolbelt](https://github.com/supabase/pg-toolbelt/blob/HEAD/AGENTS.md): what counts as a valid red test. Its PR-numbered incidents inside the rules are the antipattern this skill moves out.
- [kubernetes-sigs/cluster-api-provider-openstack](https://github.com/kubernetes-sigs/cluster-api-provider-openstack/blob/HEAD/AGENTS.md): a pitfall with its exact sequence (`make verify` compares against HEAD).
- [temporalio/sdk-java](https://github.com/temporalio/sdk-java/blob/HEAD/AGENTS.md): 59 lines at the root, detail in nested files.
- [mongodb/node-mongodb-native](https://github.com/mongodb/node-mongodb-native/blob/HEAD/AGENTS.md): a hard-coded account id in a variable shows values that drift from their source.

## House experience

The STATE.md split, the source and date on each claim, and "verify status at the primary source" are this skill's own inference, not stated by the sources above. They respond to a pattern seen in real project memory: the same status repeated in several notes, with some left stale.
