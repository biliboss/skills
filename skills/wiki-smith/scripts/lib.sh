# shellcheck shell=sh disable=SC2034
# lib.sh - shared by the wiki-smith scripts (POSIX sh, sourced, not run).
# Resolves the wiki folder and loads wiki.config (KEY=value, sh-sourceable).
#
# Wiki folder: -w DIR, else $WIKI_DIR, else ./.wiki, else <git toplevel>/.wiki.
# Config file: -c FILE, else $WIKI_CONFIG, else <wiki>/wiki.config (optional).
# The caller sets WIKI_ARG and CFG_ARG (from -w and -c) before calling wiki_resolve.

wiki_resolve() {
  WIKI=${WIKI_ARG:-${WIKI_DIR:-}}
  if [ -z "$WIKI" ]; then
    if [ -d ./.wiki ]; then
      WIKI=./.wiki
    else
      top=$(git rev-parse --show-toplevel 2>/dev/null || true)
      if [ -n "$top" ] && [ -d "$top/.wiki" ]; then WIKI=$top/.wiki; fi
    fi
  fi
  if [ -z "$WIKI" ] || [ ! -d "$WIKI" ]; then
    echo "wiki-smith: no wiki folder found (use -w DIR)" >&2
    exit 1
  fi
  WIKI=$(cd "$WIKI" && pwd -P)
  CFG=${CFG_ARG:-${WIKI_CONFIG:-$WIKI/wiki.config}}
  if [ -f "$CFG" ]; then
    # shellcheck disable=SC1090
    . "$CFG"
  elif [ -n "${CFG_ARG:-}${WIKI_CONFIG:-}" ]; then
    echo "wiki-smith: config not found: $CFG" >&2
    exit 1
  fi
  : "${DIARY_DIR:=journal}"
  : "${INBOX:=inbox.md}"
  : "${INDEX:=index.md}"
  : "${MAIN_BRANCH:=main}"
  : "${FOOTER_PREFIX:=Map:}"
  : "${HISTORY_HEADING:=## History}"
  : "${CREATED_KEY:=created}"
  : "${UPDATED_KEY:=updated}"
  : "${DAY_TITLE:=Journal of}"
  : "${PREV_LABEL:=Previous day}"
  : "${NEXT_LABEL:=Next day}"
  : "${NO_TIME_PREFIX:=no-time}"
  : "${GEN_NOTE:=Generated index (scripts/day-index.sh); do not edit. Each note is a file in \`%s/\`.}"
  DIARY=$WIKI/$DIARY_DIR
}
