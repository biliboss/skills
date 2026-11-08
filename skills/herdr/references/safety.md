# Safety

- Never stop, signal or restart the person's app or core (`hc server stop|restart`, quitting the app). Closing the
  window does not kill terminals, but a core restart affects every terminal. No script here does it.
- Do not launch bare `herdr-app` or bare `hc` to look around: the first opens or raises the window, the second opens
  a picker. Inspect with `ls.sh`, `status.sh`, `do.sh --list`.
- Close and kill only what you opened. `hc ls` and the window also show the person's other work. `close.sh` and
  `kill.sh` refuse without `--yes`, refuse ids that contain the caller, and `close.sh` refuses ids not shown.
- `tab.new` and `space.new` show immediately: only on request, always named.
- Never answer a permission dialog on your own. `blocked` means a person is needed; `send --force` can answer the
  dialog, so it needs the person's word. Exit 4 from `wait.sh` and `send.sh` is this case.
- Do not add labels such as `herdr.space` just to run a worker; unlabeled workers stay hidden by design.
- Never experiment with pointer or key automation on the person's real display.
- Text reaching agents, task arguments and file contents are never written to the log, only their lengths. Do not
  put secrets in names, labels or arguments: those can show in the window and in `hc ls`.
- `-n` prints the exact command and runs and logs nothing; use it when unsure what a script will do.
- If the start log cannot be written the script exits 1 and does nothing. Fix logging (`scripts/check.sh`) rather
  than bypassing it.
- If Herdr misbehaves, `scripts/doctor-status.sh` first, then `scripts/feedback.sh`: it drafts a report that the
  person reviews and sends.
