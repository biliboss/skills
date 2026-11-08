#!/usr/bin/env bash
# what: ag-selftest (fake panes in a throwaway herdr workspace) passes in full
out="$("$BIN/ag-selftest" 2>&1)"; rc=$?
echo "$out" | tail -1
exit $rc
