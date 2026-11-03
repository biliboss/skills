#!/bin/sh
# day-index.sh - regenerate the day index (<DIARY_DIR>/<day>.md) of every day from its notes folder.
# Usage: day-index.sh [-w WIKI_DIR] [-c CONFIG]
# Prints the files it wrote. Exit 0 ok; 2 when a day file holds text the generator does not produce
# (hand-written notes in the old format, a git conflict mark). It then writes nothing.
#
# Known limit: the original (TypeScript) also moved hand-written notes from the day file into their
# own files. Here that is an error with file:line: move each note into <day>/<HHMM>-<slug>.md
# (note.sh) and rerun. DIARY_DIR must be a folder directly under the wiki (links use ../<INBOX>).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
WIKI_ARG='' CFG_ARG=''
while getopts 'w:c:' o; do
  case $o in
    w) WIKI_ARG=$OPTARG ;;
    c) CFG_ARG=$OPTARG ;;
    *) exit 2 ;;
  esac
done
export WIKI_ARG CFG_ARG
# shellcheck source=lib.sh
. "$here/lib.sh"
wiki_resolve
[ -d "$DIARY" ] || exit 0

export LC_ALL=C
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

# Days: every folder or file named YYYY-MM-DD.
for p in "$DIARY"/*; do
  [ -e "$p" ] || continue
  b=${p##*/}
  b=${b%.md}
  case $b in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) echo "$b" ;;
  esac
done | sort -u > "$tmp/days"

gen_note() { printf '%s' "$GEN_NOTE" | sed "s|%s|$1|g"; }

# First pass: refuse day files that hold text the generator does not produce.
status=0
while read -r day; do
  f=$DIARY/$day.md
  [ -f "$f" ] || continue
  note=$(gen_note "$day")
  awk -v title="# $DAY_TITLE $day" -v map="$FOOTER_PREFIX " -v gen="$note" \
    -v rel="$DIARY_DIR/$day.md" -v day="$day" '
    BEGIN { code = 0; bad = 0 }
    /^ *```/ { code = !code }
    !code && /^(<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)( |$)/ { printf "%s:%d: git conflict mark: resolve the merge first\n", rel, NR; bad = 1; next }
    $0 == "" { next }
    index($0, title) == 1 { next }
    index($0, map) == 1 { next }
    $0 == gen { next }
    index($0, "- [") == 1 && index($0, "](" day "/") > 0 && $0 ~ /\.md\)$/ { next }
    { printf "%s:%d: line the generator does not produce (old-format note?): move it to %s/<HHMM>-<slug>.md\n", rel, NR, day; bad = 1 }
    END { exit bad ? 1 : 0 }
  ' "$f" >&2 || status=2
done < "$tmp/days"
if [ "$status" -ne 0 ]; then exit 2; fi

# Second pass: build each index and write it when it changed.
while read -r day; do
  prev=$(awk -v d="$day" '$0 < d { p = $0 } END { print p }' "$tmp/days")
  next=$(awk -v d="$day" '$0 > d { print; exit }' "$tmp/days")
  out=$tmp/$day.out
  m="$FOOTER_PREFIX [inbox](../$INBOX)"
  if [ -n "$prev" ]; then m="$m · $PREV_LABEL: [$prev]($prev.md)"; fi
  if [ -n "$next" ]; then m="$m · $NEXT_LABEL: [$next]($next.md)"; fi
  printf '# %s %s\n\n%s\n\n%s\n' "$DAY_TITLE" "$day" "$m" "$(gen_note "$day")" > "$out"
  : > "$tmp/notes"
  if [ -d "$DIARY/$day" ]; then
    for n in "$DIARY/$day"/*.md; do
      if [ -f "$n" ]; then
        b=${n##*/}
        echo "${b%.md}"
      fi
    done | sort > "$tmp/notes"
  fi
  if [ -s "$tmp/notes" ]; then
    printf '\n' >> "$out"
    while read -r base; do
      t=$(head -n 1 "$DIARY/$day/$base.md" | sed -e 's/^## //' -e 's/\[/\\[/g' -e 's/\]/\\]/g')
      printf -- '- [%s](%s/%s.md)\n' "$t" "$day" "$base" >> "$out"
    done < "$tmp/notes"
  fi
  if [ ! -f "$DIARY/$day.md" ] || ! cmp -s "$out" "$DIARY/$day.md"; then
    cp "$out" "$DIARY/$day.md"
    echo "$DIARY_DIR/$day.md"
  fi
done < "$tmp/days"
