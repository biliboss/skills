#!/usr/bin/env bash
# what: every ag-* and the scripts in ~/agents/scripts are executable and pass bash -n
ruim=""
for f in "$BIN"/ag-* "$AG_HOME"/scripts/*.sh; do
  [ -f "$f" ] || continue
  [ -x "$f" ] || [ "$(basename "$f")" = ag-lib.sh ] || ruim="$ruim $(basename "$f")(not executable)"
  bash -n "$f" 2>/dev/null || ruim="$ruim $(basename "$f")(syntax)"
done
[ -z "$ruim" ] && echo "all executable and with valid syntax" || { echo "problems:$ruim"; exit 1; }
