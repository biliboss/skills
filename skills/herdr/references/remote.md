# Remote machines

Syntax: `hc --skill` (section on other machines and files), `hc help machine`, `hc <command> --help`.

- Your own file tools touch only the machine you run on. For remote paths use `scripts/remote-file.sh`
  (`hc file ... --on M`), for one-shot commands `scripts/remote-exec.sh` (`hc exec --on M`), and for terminals that
  stay alive `scripts/spawn.sh --on M` or `scripts/run.sh --on M`.
- A terminal started on a machine has a full address such as `vps/t3`. Use that whole address with `wait.sh`,
  `read.sh`, `send.sh` and the rest.
- `scripts/machines.sh` lists the machines added here. Adding, renaming, updating or removing one is the person's
  setup (`hc machine add|rename|update|rm`); do not do it unasked. `hc machine update` restarts hc there.
- Remote paths start at that machine's home unless you pass `--cwd`; local paths start at the current folder. Prefer
  explicit paths.
- `remote-exec.sh` runs argv as given, with no shell; pass `sh -c '...'` yourself when you need one. Its default
  timeout is 60 seconds (at most 600); a timeout exits 3.
- `remote-file.sh write` replaces the whole file and creates missing folders. `edit` needs the old text exactly once;
  `edit_failed` means add context to make it unique. Several `--old/--new` pairs apply all or none.
- A window space can live on a machine too (`space-new.sh --machine M --folder DIR`): the folder is on that machine,
  and tabs and splits made in that space stay there.
- Only lengths are logged for remote commands and file contents, never the content itself.
