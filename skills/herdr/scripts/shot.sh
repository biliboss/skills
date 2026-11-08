#!/usr/bin/env bash
# shot.sh - save the window's last frame as a PNG and print its absolute path. Then look at the picture.
# Usage: shot.sh [FILE.png]
# Default file: $TMPDIR/herdr-shot-<pid>.png. It needs a running window that has drawn a frame; it does not
# change the window, so it is not logged.
# Exit: 0 ok; 1 no window or no frame; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -le 1 ] || hl_usage_err "at most one FILE"
hl_need herdr-app
herdr-app shot "${1:-${TMPDIR:-/tmp}/herdr-shot-$$.png}" || hl_die 1 "no screenshot: is the window open and drawn?"
