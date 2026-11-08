# shellcheck shell=sh disable=SC2034
# lib.sh - shared by the wiki-smith scripts (POSIX sh, sourced, not run).
# Resolves the wiki folder and loads wiki.config (KEY=value, sh-sourceable).
#
# Settings: a variable already set in the environment wins, then the file
# $WIKI_SKILL_ENV, or by default .env in the folder above scripts/ (found
# through the caller's $here): WIKI_HOME (default $HOME/wiki), WIKI_REPO
# (default biliboss/wiki), WIKI_REMOTE (default git@github.com:$WIKI_REPO.git).
#
# $WIKI_HOME is a git checkout of $WIKI_REMOTE with one folder per project.
# When the folder is not given explicitly (no -w, no $WIKI_DIR), wiki_resolve
# maintains it before choosing the project: a missing or empty one is cloned
# (a failed clone is an error), one holding .git is fast-forwarded (a failed
# pull warns once and work continues); a folder that has files but no .git is
# left alone. It never stashes, resets or cleans.
#
# Wiki folder, first hit: -w DIR; $WIKI_DIR; $WIKI_HOME/$WIKI_PROJECT (-P
# PROJECT, error if missing); the $WIKI_HOME project whose wiki.config
# REPO=owner/name matches the origin remote of the current git repo;
# $WIKI_HOME/biliboss. REPO= is read without sourcing the config.
# Config file: -c FILE, else $WIKI_CONFIG, else <wiki>/wiki.config (optional).
# The caller sets WIKI_ARG, CFG_ARG and WIKI_PROJECT (from -w, -c, -P) before
# calling wiki_resolve.

_lib_env=${WIKI_SKILL_ENV:-${here:+$here/../.env}}
if [ -n "$_lib_env" ] && [ -f "$_lib_env" ]; then
  for _lib_v in WIKI_HOME WIKI_REPO WIKI_REMOTE; do
    if eval "[ -z \"\${$_lib_v:-}\" ]"; then
      _lib_val=$(sed -n "s/^$_lib_v=//p" "$_lib_env" | head -n 1)
      if [ -n "$_lib_val" ]; then eval "$_lib_v=$_lib_val"; fi
    fi
  done
fi
unset _lib_env _lib_v _lib_val

wiki_resolve() {
  : "${WIKI_HOME:=$HOME/wiki}"
  : "${WIKI_REPO:=biliboss/wiki}"
  : "${WIKI_REMOTE:=git@github.com:$WIKI_REPO.git}"
  WIKI=${WIKI_ARG:-${WIKI_DIR:-}}
  if [ -z "$WIKI" ]; then
    if [ -e "$WIKI_HOME/.git" ]; then
      if ! git -C "$WIKI_HOME" pull --ff-only --quiet 2>/dev/null; then
        echo "wiki-smith: could not fast-forward $WIKI_HOME; using the local copy" >&2
      fi
    elif [ ! -e "$WIKI_HOME" ] || [ -z "$(ls -A "$WIKI_HOME" 2>/dev/null)" ]; then
      if ! git clone --quiet "$WIKI_REMOTE" "$WIKI_HOME"; then
        echo "wiki-smith: could not clone $WIKI_REMOTE into $WIKI_HOME" >&2
        exit 1
      fi
    fi
  fi
  if [ -z "$WIKI" ] && [ -n "${WIKI_PROJECT:-}" ]; then
    WIKI=$WIKI_HOME/$WIKI_PROJECT
    if [ ! -d "$WIKI" ]; then
      echo "wiki-smith: project wiki not found: $WIKI" >&2
      exit 1
    fi
  fi
  if [ -z "$WIKI" ]; then
    remote=$(git remote get-url origin 2>/dev/null || true)
    case $remote in
      git@github.com:*)     repo=${remote#git@github.com:} ;;
      https://github.com/*) repo=${remote#https://github.com/} ;;
      *)                    repo= ;;
    esac
    repo=${repo%.git}
    if [ -n "$repo" ]; then
      for c in "$WIKI_HOME"/*/wiki.config; do
        [ -f "$c" ] || continue
        if [ "$(sed -n 's/^REPO=//p' "$c" | head -n 1)" = "$repo" ]; then
          WIKI=${c%/wiki.config}
          break
        fi
      done
    fi
  fi
  if [ -z "$WIKI" ]; then
    WIKI=$WIKI_HOME/biliboss
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
