#!/bin/sh
# sync.sh - commit the given paths (and only them), optionally publish to origin/<MAIN_BRANCH>.
# Usage: sync.sh [-w WIKI_DIR] [-P PROJECT] [-c CONFIG] -m "message" [-p] PATH...
#        sync.sh [-w WIKI_DIR] [-P PROJECT] [-c CONFIG] -W
#   -m  commit message (required; add the attribution lines your repo asks for, with a blank line)
#   -P  the project folder inside $WIKI_HOME, instead of -w DIR
#   -p  push: fetch, rebase onto origin/<main>, `git push origin HEAD:<main>`. Without -p nothing is
#       published. Use -p only when the user asked to sync.
#   -W  create a fresh worktree from origin/<main> on a branch wiki-sync/<time> and print its path.
#       Edit there (the wiki is <worktree>/<same path as here>), run dates.sh, day-index.sh and lint.py
#       there, then run `sync.sh -m ... [-p] PATH...` from inside it. This is the way to touch shared
#       files (index, inbox) when another session may also have edited them.
#
# Every mode runs lint.py on exactly what will be committed and never commits or pushes a red lint.
#
# In place: the checkout is on <main>, not behind origin/<main>, and has no changes outside PATH...
# Carry (worktree): otherwise (behind, another branch, or someone else's changes) work in a fresh
#   `git worktree` from origin/<main>: carry the changes of PATH... there (git apply --3way), commit,
#   and, with -p, rebase, push, then restore PATH... in the checkout and fast-forward it (never
#   touching other people's modified files). Without -p the worktree is removed and the commit stays on
#   a local branch wiki-sync/<time>, which is printed.
#   The generated day indexes (<DIARY_DIR>/YYYY-MM-DD.md) are never carried: they are regenerated in
#   the worktree with day-index.sh, so they list only notes that are in the commit.
#   Limit: sync.sh cannot tell which hunks of a hand-edited shared file (index, inbox) are yours. The
#   carry takes the whole diff of the file; if that diff links to pages that are not carried, the lint
#   fails and nothing is published. Foreign lines that do not break the lint are carried too: when
#   another session may have edited the same file, use -W and edit it in the worktree.
# From inside a -W worktree (branch wiki-sync/*): commits in place; with -p rebases, pushes, fast-forwards
#   the main checkout where it can and removes the worktree.
#
# Failure (lint red, conflict, rebase or push failure): exit 1, the checkout is left as it was, and the
#   carry worktree is removed (a -W worktree is yours and is left for inspection).
# Exit 0: ok. After a successful push the checkout fast-forward is best effort: if it cannot be done
#   (the local <main> diverged, or other sessions' modified files overlap) it prints why and still exits 0.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
WIKI_ARG='' CFG_ARG='' msg='' push=0 mkwt=0
while getopts 'w:c:m:pWP:' o; do
  case $o in
    w) WIKI_ARG=$OPTARG ;;
    c) CFG_ARG=$OPTARG ;;
    m) msg=$OPTARG ;;
    p) push=1 ;;
    W) mkwt=1 ;;
    P) WIKI_PROJECT=$OPTARG ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [ "$mkwt" -eq 0 ] && { [ -z "$msg" ] || [ $# -eq 0 ]; }; then
  echo 'usage: sync.sh [-w DIR] [-P PROJECT] [-c CONFIG] -m "message" [-p] PATH...' >&2
  echo '       sync.sh [-w DIR] [-P PROJECT] [-c CONFIG] -W' >&2
  exit 2
fi
export WIKI_ARG CFG_ARG WIKI_PROJECT
# shellcheck source=lib.sh
. "$here/lib.sh"
wiki_resolve

repo=$(git -C "$WIKI" rev-parse --show-toplevel)
main=$MAIN_BRANCH
orig=$(pwd -P)
cd "$repo"
wiki_rel=${WIKI#"$repo"/}
diary_rel=$wiki_rel/$DIARY_DIR
dayglob=":(exclude,glob)$diary_rel/????-??-??.md"

has_remote=0
if git remote get-url origin >/dev/null 2>&1; then has_remote=1; fi
if [ "$has_remote" -eq 1 ]; then git fetch --prune --quiet origin; fi

# lint_at ROOT: lint the wiki as it is under ROOT (the checkout or a worktree). Prints the problems.
lint_at() {
  if [ -n "$CFG_ARG" ]; then
    case $CFG_ARG in
      "$repo"/*) cfg=$1/${CFG_ARG#"$repo"/} ;;
      *) cfg=$CFG_ARG ;;
    esac
    python3 -I "$here/lint.py" -w "$1/$wiki_rel" -c "$cfg"
  else
    python3 -I "$here/lint.py" -w "$1/$wiki_rel"
  fi
}

branch=$(git symbolic-ref --short -q HEAD || true)

if [ "$mkwt" -eq 1 ]; then
  if [ "$has_remote" -eq 0 ]; then echo "sync.sh: -W needs an origin to branch from" >&2; exit 1; fi
  wt=$(cd "$(mktemp -d)" && pwd -P)
  git worktree add -q -b "wiki-sync/$(date -u +%Y%m%d%H%M%S)-$$" "$wt" "origin/$main"
  echo "$wt"
  echo "wiki-smith: edit under $wt/$wiki_rel, then run sync.sh -m ... [-p] PATH... from $wt" >&2
  exit 0
fi

# Paths relative to the repo root (they are given relative to the current directory or absolute).
paths_file=$(mktemp)
trap 'rm -f "$paths_file" "$paths_file".*' EXIT HUP INT TERM
for p in "$@"; do
  case $p in
    /*) abs=$p ;;
    *) abs=$orig/$p ;;
  esac
  d=$(dirname "$abs")
  b=$(basename "$abs")
  if [ -d "$d" ]; then abs=$(cd "$d" && pwd -P)/$b; fi
  rel=${abs#"$repo"/}
  if [ "$rel" = "$abs" ]; then
    echo "sync.sh: $p is outside the repository" >&2
    exit 1
  fi
  printf '%s\n' "$rel" >> "$paths_file"
done

# Does the checkout have changes outside PATH...?
in_paths() {
  while IFS= read -r p; do
    case $1 in
      "$p" | "$p"/*) return 0 ;;
    esac
  done < "$paths_file"
  return 1
}
others=''
git status --porcelain --untracked-files=all | sed 's/^...//' | sed 's/^"\(.*\)"$/\1/' > "$paths_file.status"
while IFS= read -r f; do
  if ! in_paths "$f"; then others="$others$f
"; fi
done < "$paths_file.status"
rm -f "$paths_file.status"
behind=0
if [ "$has_remote" -eq 1 ]; then behind=$(git rev-list --count "HEAD..origin/$main" 2>/dev/null || echo 0); fi

add_paths() { while IFS= read -r p; do git add -A -- "$p"; done < "$paths_file"; }
commit_paths() {
  # Commit only the staged PATH... (nothing else staged by us): `--` limits the commit to the paths.
  set --
  while IFS= read -r p; do set -- "$@" "$p"; done < "$paths_file"
  if git diff --cached --quiet -- "$@"; then
    echo "sync.sh: nothing to commit in the given paths" >&2
    return 3
  fi
  git commit -q -m "$msg" -- "$@"
}

is_dayindex() { case $1 in "$diary_rel"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md) return 0 ;; esac; return 1; }
is_shared() { [ "$1" = "$wiki_rel/$INDEX" ] || [ "$1" = "$wiki_rel/$INBOX" ]; }

# main_checkout: the first worktree listed is the main checkout.
main_checkout() { git worktree list --porcelain | sed -n '1s/^worktree //p'; }

# finish_checkout DIR BRANCH LOSSLESS_ONLY (0|1): after a push, bring the main checkout DIR up to
# origin/<main> without touching other sessions' files. Never fails the run (the push already worked).
finish_checkout() {
  fc_dir=$1 fc_branch=$2 fc_lossless=$3
  (
    cd "$fc_dir"
    git fetch -q origin
    if [ "$fc_branch" != "$main" ]; then
      echo "pushed to origin/$main; the checkout is on '$fc_branch', left as is"
      exit 0
    fi
    if ! git merge-base --is-ancestor HEAD "origin/$main"; then
      echo "pushed to origin/$main; local $main has commits that are not on origin/$main (diverged), so it was not fast-forwarded and your edited files were left as they are (already on origin/$main): git checkout -- <those files>, then git pull --rebase"
      exit 0
    fi
    # Our paths are now upstream: restore them in the checkout so the fast-forward can proceed, but never
    # discard an edit that is not upstream. A file identical to origin/<main> is restored (nothing is lost);
    # a generated day index is restored (it is regenerated); a hand-edited shared file (index, inbox) that
    # differs from origin/<main> may hold another session's lines, so it is kept; with lossless-only (-W
    # worktree: the edits were made elsewhere) every file that differs is kept.
    set --
    while IFS= read -r p; do set -- "$@" "$p"; done < "$paths_file"
    git ls-files -m -- "$@" > "$paths_file.mod"
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      if git show "origin/$main:$f" 2>/dev/null | cmp -s - "$f"; then
        git checkout -q HEAD -- "$f" 2>/dev/null || true
      elif is_dayindex "$f"; then
        git checkout -q HEAD -- "$f" 2>/dev/null || true
      elif [ "$fc_lossless" -eq 0 ] && ! is_shared "$f"; then
        git checkout -q HEAD -- "$f" 2>/dev/null || true
      fi
    done < "$paths_file.mod"
    if [ -f "$paths_file.untracked" ]; then
      while IFS= read -r u; do
        [ -n "$u" ] || continue
        if is_dayindex "$u" || git show "origin/$main:$u" 2>/dev/null | cmp -s - "$u"; then rm -f "$u"; fi
      done < "$paths_file.untracked"
    fi
    if git merge --ff-only -q "origin/$main" 2>/dev/null; then
      echo "pushed and fast-forwarded $main"
    else
      echo "pushed; $main could not be fast-forwarded: local edits overlap (a shared file such as the index or inbox, or another session's files). Your changes are already on origin/$main; when the local edit is only yours, run git checkout -- <file>, then git merge --ff-only origin/$main"
    fi
  )
}

# ---- Inside a -W worktree: commit in place, publish from here.
git_dir=$(git rev-parse --git-dir)
common_dir=$(git rev-parse --git-common-dir)
case $branch in
  wiki-sync/*)
    if [ "$(cd "$git_dir" && pwd)" != "$(cd "$common_dir" && pwd)" ]; then
      lint_out=$(lint_at "$repo") || { printf '%s\n' "$lint_out" >&2; echo "sync.sh: lint is red; nothing committed (the worktree $repo is left for inspection)" >&2; exit 1; }
      add_paths
      rc=0
      commit_paths || rc=$?
      if [ "$rc" -eq 3 ]; then exit 0; elif [ "$rc" -ne 0 ]; then exit 1; fi
      if [ "$push" -eq 0 ]; then
        git log -1 --format="committed %h %s (local branch $branch in $repo; rerun with -p to publish)"
        exit 0
      fi
      git fetch -q origin
      git rebase -q "origin/$main" || { git rebase --abort >/dev/null 2>&1 || true; echo "sync.sh: rebase failed; the commit is on branch $branch in $repo" >&2; exit 1; }
      lint_out=$(lint_at "$repo") || { printf '%s\n' "$lint_out" >&2; echo "sync.sh: lint is red after the rebase; not pushed (the worktree $repo is left for inspection)" >&2; exit 1; }
      git push -q origin "HEAD:$main" || { echo "sync.sh: push failed; the commit is on branch $branch in $repo" >&2; exit 1; }
      mc=$(main_checkout)
      mb=$(git -C "$mc" symbolic-ref --short -q HEAD || true)
      : > "$paths_file.untracked"
      finish_checkout "$mc" "$mb" 1
      cd "$mc"
      git worktree remove --force "$repo" >/dev/null 2>&1 || true
      git branch -D "$branch" >/dev/null 2>&1 || true
      git log -1 --format="origin/$main at %h %s" "origin/$main" 2>/dev/null || true
      exit 0
    fi
    ;;
esac

# ---- In place.
if [ "$branch" = "$main" ] && [ "$behind" -eq 0 ] && [ -z "$others" ]; then
  # Nothing outside PATH is modified, so the checkout is exactly what will be committed.
  lint_out=$(lint_at "$repo") || { printf '%s\n' "$lint_out" >&2; echo "sync.sh: lint is red; nothing committed" >&2; exit 1; }
  add_paths
  rc=0
  commit_paths || rc=$?
  if [ "$rc" -eq 3 ]; then exit 0; elif [ "$rc" -ne 0 ]; then exit 1; fi
  if [ "$push" -eq 1 ]; then git push -q origin "HEAD:$main"; fi
  git log -1 --format='committed %h %s'
  exit 0
fi

# ---- Carry: worktree from origin/<main>.
if [ "$has_remote" -eq 0 ]; then
  echo "sync.sh: the checkout is not clean for an in-place commit and there is no origin to branch from" >&2
  exit 1
fi
wt=$(cd "$(mktemp -d)" && pwd -P)
newbranch=wiki-sync/$(date -u +%Y%m%d%H%M%S)-$$
cleanup() { git worktree remove --force "$wt" >/dev/null 2>&1 || rm -rf "$wt"; }
git worktree add -q -b "$newbranch" "$wt" "origin/$main"

fail() {
  echo "sync.sh: $1" >&2
  cleanup
  git branch -D "$newbranch" >/dev/null 2>&1 || true
  exit 1
}

# Carry the changes: tracked edits as a 3-way patch, untracked files by copy. Generated day indexes
# are left out (regenerated below).
tracked_patch=$(mktemp)
set --
while IFS= read -r p; do set -- "$@" "$p"; done < "$paths_file"
git diff HEAD --binary -- "$@" "$dayglob" > "$tracked_patch"
if [ -s "$tracked_patch" ]; then
  (cd "$wt" && git apply --3way --index "$tracked_patch") || { rm -f "$tracked_patch"; fail "could not apply your changes on origin/$main (conflict); resolve in the checkout and rerun"; }
fi
rm -f "$tracked_patch"
git ls-files --others --exclude-standard -- "$@" "$dayglob" > "$paths_file.carried"
while IFS= read -r f; do
  if [ -e "$wt/$f" ]; then fail "$f is new here but already exists on origin/$main"; fi
  mkdir -p "$wt/$(dirname "$f")"
  cp -p "$f" "$wt/$f"
done < "$paths_file.carried"
# Untracked files to remove from the checkout after the push: the carried ones and the day indexes.
git ls-files --others --exclude-standard -- "$@" > "$paths_file.untracked"

set +e
(
  cd "$wt"
  while IFS= read -r p; do
    if [ -e "$p" ] || git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then git add -A -- "$p"; fi
  done < "$paths_file"
  # Day indexes: regenerate here so they list only the notes that are in this worktree.
  if git status --porcelain | grep -q " $diary_rel/" || git status --porcelain | grep -q " $diary_rel\$"; then
    if [ -n "$CFG_ARG" ]; then
      case $CFG_ARG in
        "$repo"/*) cfg=$wt/${CFG_ARG#"$repo"/} ;;
        *) cfg=$CFG_ARG ;;
      esac
      sh "$here/day-index.sh" -w "$wt/$wiki_rel" -c "$cfg" >/dev/null || exit 4
    else
      sh "$here/day-index.sh" -w "$wt/$wiki_rel" >/dev/null || exit 4
    fi
    git add -A -- "$diary_rel"
  fi
  if git diff --cached --quiet; then exit 3; fi
)
rc=$?
set -e
if [ "$rc" -eq 3 ]; then
  cleanup
  git branch -D "$newbranch" >/dev/null 2>&1 || true
  echo "sync.sh: nothing to commit in the given paths" >&2
  exit 0
elif [ "$rc" -eq 4 ]; then
  fail "day-index.sh failed in the worktree (old-format note or conflict mark in a day file); nothing committed"
elif [ "$rc" -ne 0 ]; then
  fail "staging failed"
fi

lint_out=$(lint_at "$wt") || { printf '%s\n' "$lint_out" >&2; fail "lint is red on what would be committed (a problem already on origin/$main, or the diff of a shared file carrying another session's lines that link to files not carried); nothing committed or pushed, checkout untouched, worktree removed. Use sync.sh -W and edit in the worktree instead"; }
(cd "$wt" && git commit -q -m "$msg") || fail "commit failed"

if [ "$push" -eq 0 ]; then
  cleanup
  echo "committed on local branch $newbranch (not pushed); rerun with -p to publish the paths from the checkout"
  exit 0
fi

(
  cd "$wt"
  git fetch -q origin
  git rebase -q "origin/$main" || { git rebase --abort >/dev/null 2>&1 || true; exit 1; }
  lint_at "$wt" >/dev/null || exit 5
  git push -q origin "HEAD:$main"
) || {
  echo "sync.sh: rebase, lint or push failed; the commit is kept on local branch $newbranch, the checkout is untouched, the worktree was removed" >&2
  cleanup
  exit 1
}

finish_checkout "$repo" "$branch" 0
cleanup
git branch -D "$newbranch" >/dev/null 2>&1 || true
git log -1 --format="origin/$main at %h %s" "origin/$main" 2>/dev/null || true
