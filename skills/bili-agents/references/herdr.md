# Desktop transport

The current scripts use `hc` (herdr-core) addresses such as `t12` and `herdr-app do terminal.open`. The older `herdr` server CLI is a separate backend and is not used by these tools.

Inspect a target before typing. `ag-send` sends text and Enter separately, uses bracketed paste for multiline input, and stops when a permission prompt appears. `ag-read --state` distinguishes working, waiting, permission, menu, unsent and idle states from screen markers; verify those markers when the terminal client changes.

`ag-spawn -n` describes the proposed session without opening a terminal or writing settings. Actual startup generates one settings file under `AG_HOME/.run`, with the SessionStart role loader, notification hooks and the plugin output style. Instances created with `ag-new` store only a role name and project context. Never copy private project rules into a generic role card.

`ag-selftest` creates its own disposable workspace. Run it only in an authorized desktop environment. `ag-wait` uses the event stream and settled state rather than repeatedly reading panes; Stop events alone are not delivery evidence.
