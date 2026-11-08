#!/usr/bin/env bash
# tab-new.sh - make a NAMED tab in a space. It appears at once: only when the person asked for it.
# Usage: tab-new.sh [-n] [--json] --name NAME [--space ID] [--folder DIR] [--argv JSON] [--task TEXT|-]
# --space defaults to the shown one; --argv is a JSON array (an agent); --task its first message ("-" = stdin).
# stdout: key<TAB>value of the ids created (--json: raw). The task text is never logged, only its length.
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need herdr-app jq
hl_kv "name space folder argv task" "name" "$@"
obj=$(hl_obj "${OBJARGS[@]}") || exit 1
name=$(jq -r .name <<<"$obj")
hl_op "$name" "$TASKLEN" hl_app_do tab.new "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
