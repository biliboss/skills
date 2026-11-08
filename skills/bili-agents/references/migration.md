# Diagnostic migration

The legacy entrypoint and flags remain available. `ag-doctor --contract` selects the strict YAML runner. It preserves observed exit/output from each shell check, but a green observation without confirmed red proof is `PEND` in the strict report. The legacy `PROMOTE` state therefore does not map to strict `PASS` automatically.

Checks are classified before execution. File syntax, dry-run startup, role cards, report formatting, notification dry runs and isolated instance integration are fast checks. Desktop reachability, manager registration and installed state are runtime checks. Disposable desktop self-tests and fresh model voice behavior are journeys.

The public migration excludes the old server CLI diagnostic and checks tied to house script cleanup, a particular tool installation or migration of existing private instances. Keep machine-specific checks under the configured house doctor directory; the portable contract never embeds their configuration.

Verification performed with an isolated empty agent home:

- Ten safe migrated checks returned equivalent normalized JSON and exit codes through the wrapper and retained legacy command.
- All nine fast checks executed successfully through the strict runner and remained pending because no matching red proof was confirmed.
- Role and instance integration first failed because the hacker role card was absent, then passed after implementation. Raw output lives in the user's local state directory; it is not shipped as transferable proof.

Runtime desktop state and live fresh-session voice behavior require their own environment and evidence. Do not interpret the isolated checks as that proof.
