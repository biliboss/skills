# Executable capability contracts

The YAML interpreter is separate from the generic five-dimension doctor:

```sh
uv run --script skills/doctor/scripts/contracts.py --root .
skills/doctor/scripts/doctor runtime apps/example
skills/doctor/scripts/doctor journey --capability checkout
skills/doctor/scripts/doctor --all --json
skills/doctor/scripts/doctor --changed --base origin/main
```

Default selection runs fast checks. runtime and journey select exactly those kinds. --all selects all kinds and
assesses success. --changed includes tracked staged/unstaged changes, untracked files and both paths of renames;
--base adds changes since a Git merge base for CI. Each file selects its nearest ancestral contract.
Uncovered files appear in the report and prevent an approved changed selection. All discovered contracts validate
before any command runs. Selection paths are relative to --root. No contracts or an empty normal selection is a usage error.

```yaml
# .doctor.yaml, beside the app/library it describes
doctor:
  timeout: 30
  allowed_hosts: [localhost]
capabilities:
  greeting:
    intent: A visitor receives a greeting.
    checks:
      - id: greeting-text
        kind: fast
        expected: The greeting says hello.
        red: The existing greeting does not contain hello.
        remedy: Implement the greeting text.
        grep: {path: greeting.txt, pattern: hello}
      - id: greeting-live
        kind: runtime
        expected: The local service is healthy.
        red: The running service returns an unhealthy status.
        remedy: Correct service startup and health handling.
        http: {url: 'http://localhost:8080/health', status: 200}
    keep: [greeting-text]
    success: [keep, greeting-live]
```

Each check has a unique id (within the contract), explicit kind, expected, red, remedy and exactly one executor.
keep and success refer to check IDs in the same capability; `keep` in success expands the keep list. keep is always
required. success is a nonempty list. Any selected failing or pending check prevents a green selection, even if it
is not named in success. Full capability success requires every check to have been selected.

Executors:

| Key | Definition |
| --- | --- |
| file | Relative path that must exist |
| grep | `{path: relative-file, pattern: regex}` |
| schema | `{path: JSON-file, schema: inline-JSON-Schema}` |
| cli | `{command: [program, argument]}` |
| run | `{command: [program, script], why_script: explanation}` |
| http | `{url: URL, status: 200}`; hostname must occur in doctor.allowed_hosts; redirects are not followed |
| sql | `{query: SQL, read_only: true}`; explicit adapter required |
| browser | `{url: test-URL, test_environment: true}`; explicit adapter required |
| agent | `{task: description}`; explicit adapter required; missing adapter is PEND |

Optional check fields: category, timeout (positive seconds, at most 3600), scripts (relative files contributing to
evidence hashing). Local argv files are hashed automatically. Declare imported helpers in scripts; transitive
imports cannot be inferred. Paths cannot escape the contract directory. `run` is for logic unsupported by a primitive.
Commands are argv arrays, with no implicit shell. They inherit the caller's environment and run beside the contract.
Use read-only checks; the runner executes declared commands and cannot sandbox arbitrary code.

Adapters are trusted argv commands under `doctor.adapters.sql|browser|agent`. They receive one JSON document on
stdin (`executor`, `definition`). SQL additionally receives `transaction.begin = BEGIN TRANSACTION READ ONLY` and
`transaction.end = ROLLBACK`. The adapter must enforce that transaction on its database driver; use a read-only
account too. Browser adapters must target a disposable test environment. Exit 0 means the assertion holds;
nonzero is a failure, not proof of red until reviewed. Missing adapters remain PEND.

## Red evidence

```sh
doctor --record-red greeting-text
# Read observed output and its printed SHA256, then explicitly attest the declared reason:
doctor --record-red greeting-text --confirm-red 'The existing greeting does not contain hello.' \
  --confirm-observed '<SHA256 from the observed failure>'
# Correct the behavior and run:
doctor --all
```

Confirmation runs the check again but confirms the previously recorded output. Review must reject infrastructure
errors even when a custom script returns exit 1; arbitrary scripts cannot be semantically classified automatically.
Timeouts, missing executables and absent adapters cannot record red. Green without confirmed red is PEND.
Proofs live under `$XDG_STATE_HOME/doctor` (default `~/.local/state/doctor`), keyed by repository, contract-relative
path and check ID. They contain the definition hash, referenced script contents hash, observed output and explicit
confirmation. --state-dir must be outside the repository. Do not publish these private proofs.

Text output contains expected, observed, evidence, remedy, category and FOR AGENTS. --json emits one object with
results, capabilities, uncovered and summary. Internal/contract errors go only to stderr.
Exit codes: 0 selected checks approved; 1 failure/pending/uncovered; 2 usage/invalid contract; 3 timeout.
The generic doctor.py interface and exit codes remain unchanged.
