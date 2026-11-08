#!/usr/bin/env bash
# category: Runtime
# what: ag-spawn opens the agent as a split to the right of the manager, with a generated --settings (ping hooks, role loader, shared voice); dry run
# fix: make ag-spawn build `herdr-app do terminal.open ... --argv [env AG_ROLE=<role>] claude --settings $AG_HOME/.run/<agent>.settings.json [--continue]` and validate the name (exit 2) and the folder (exit 1)
[ -x "$BIN/ag-spawn" ] || { echo "ag-spawn does not exist yet"; exit 1; }
out="$("$BIN/ag-spawn" -n --role hacker demo-agent "$AG_HOME" 2>&1)" || { echo "dry run failed: $out"; exit 1; }
for parte in 'herdr-app do terminal.open' '--place right' '--name demo-agent' '--folder' 'AG_ROLE=hacker' 'claude' '--settings' '.run/demo-agent.settings.json'; do
  case "$out" in *"$parte"*) ;; *) echo "dry run does not show '$parte': $out"; exit 1 ;; esac
done
case "$out" in *"--continue"*) echo "without --continue there must be no --continue in the command: $out"; exit 1 ;; esac
out2="$("$BIN/ag-spawn" -n --continue demo-agent "$AG_HOME" 2>&1)" || { echo "dry run with --continue failed: $out2"; exit 1; }
case "$out2" in *"--continue"*) ;; *) echo "--continue does not add --continue to claude: $out2"; exit 1 ;; esac
[ ! -e "$AG_HOME/.run/demo-agent.settings.json" ] || { echo "a dry run must not write the settings file"; exit 1; }
"$BIN/ag-spawn" -n 'Bad Name' >/dev/null 2>&1; [ $? -eq 2 ] || { echo "an invalid name should exit with 2"; exit 1; }
"$BIN/ag-spawn" -n no-such-folder-xyz >/dev/null 2>&1; [ $? -eq 1 ] || { echo "a missing folder should exit with 1"; exit 1; }
echo "dry run shows the split with name, folder, role, generated settings and --continue; rejects an invalid name (2) and a missing folder (1)"
