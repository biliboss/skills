#!/usr/bin/env bash
# space-new.sh - make a NAMED space. It appears at once: only when the person asked for it.
# Usage: space-new.sh [-n] [--json] --name NAME [--folder DIR] [--machine M] [--tab TAB] [--argv JSON] [--task TEXT|-]
# --argv is a JSON array (an agent); --task is its first message ("-" reads stdin). --machine: see machines.sh.
# stdout: key<TAB>value of the ids created (--json: raw). The task text is never logged, only its length.
# Exit: 0 ok; 1 failed; 2 usage; 5 done but the end log failed. -n prints the command and does nothing.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
hl_need herdr-app jq
hl_kv "name folder machine tab argv task" "name" "$@"
obj=$(hl_obj "${OBJARGS[@]}") || exit 1
name=$(jq -r .name <<<"$obj")
hl_op "$name" "$TASKLEN" hl_app_do space.new "$obj"; rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then exit $rc; fi
if [ "$DRY" != 1 ]; then hl_print; fi
exit $rc
