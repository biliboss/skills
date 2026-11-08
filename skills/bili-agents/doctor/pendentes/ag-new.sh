#!/usr/bin/env bash
# what: ag-new creates an instance from a role and a project (a dry run with -n writes nothing)
[ -x "$BIN/ag-new" ] || { echo "ag-new does not exist yet"; exit 1; }
out="$("$BIN/ag-new" -n demo-project --papel hipster --projeto demo-project 2>&1)" || { echo "dry run failed: $out"; exit 1; }
case "$out" in *papel*projeto*|*projeto*papel*) echo "dry run describes role and project" ;; *) echo "dry run does not mention role and project: $out"; exit 1 ;; esac
