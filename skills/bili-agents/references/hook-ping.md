# Completion notifications

`manager-send-back.sh` handles Stop, AskUserQuestion and Notification events. `ag-spawn` wires these hooks into the session settings; opening a session manually does not install them.

The recipient is the caller saved in the terminal's `asker` label. `PING_ASKER` can select a recipient explicitly; the reserve manager is read from `AG_HOME/.manager-pane`. It never sends a notification to its own terminal. `--quem` reports the selected recipient.

`PING_DRY=1` prints without sending or appending an event. `PING_PAINEL=0` disables terminal delivery while preserving the event log. `AG_EVENTS` selects the event file. The hook always exits successfully so a notification error cannot block a session.

Stop fires whenever a model pauses, including pauses for workers. Require settled idleness and inspect delivery evidence before declaring completion.
