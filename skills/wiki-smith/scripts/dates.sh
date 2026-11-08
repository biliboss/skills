#!/bin/sh
# dates.sh - keep the created/updated frontmatter of the wiki's root pages (dates in UTC, from git).
# Usage: dates.sh [-w WIKI_DIR] [-P PROJECT] [-c CONFIG]
#
# A page without the dates gets CREATED_KEY from its first commit (following renames) and UPDATED_KEY
# from its last commit; a page without commits gets today. A page whose text, frontmatter aside,
# differs from HEAD gets UPDATED_KEY = today. So running it twice changes nothing. Pages ignored by
# git and empty pages are skipped. Prints the files it wrote. WIKI_TODAY overrides the date (tests).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
WIKI_ARG='' CFG_ARG=''
while getopts 'w:c:P:' o; do
  case $o in
    w) WIKI_ARG=$OPTARG ;;
    c) CFG_ARG=$OPTARG ;;
    P) WIKI_PROJECT=$OPTARG ;;
    *) exit 2 ;;
  esac
done
export WIKI_ARG CFG_ARG WIKI_PROJECT
# shellcheck source=lib.sh
. "$here/lib.sh"
wiki_resolve

today=${WIKI_TODAY:-$(date -u +%Y-%m-%d)}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

g() { TZ=UTC git -C "$WIKI" "$@" 2>/dev/null || true; }

# Frontmatter: line 1 is '---' and the closing '---' is the first one at line 3 or later.
# Prints the number of the closing line, or nothing.
fm_end() {
  awk 'NR == 1 { if ($0 != "---") exit; next } NR >= 3 && $0 == "---" { print NR; exit }' "$1"
}
# Body (text after the frontmatter) of a file into $2.
body_of() {
  e=$(fm_end "$1")
  if [ -n "$e" ]; then tail -n +$((e + 1)) "$1" > "$2"; else cat "$1" > "$2"; fi
}
# Value of a top-level key in the frontmatter of $1 (empty when absent); has_key tells presence.
fm_get() {
  e=$(fm_end "$1")
  [ -n "$e" ] || return 0
  sed -n "2,$((e - 1))p" "$1" | awk -v k="$2" '
    /^[ \t]/ { next }
    { i = index($0, ":"); if (i > 1) { key = substr($0, 1, i - 1); gsub(/^[ \t]+|[ \t]+$/, "", key)
        if (key == k) { v = substr($0, i + 1); gsub(/^[ \t]+|[ \t]+$/, "", v); print v; exit } } }'
}
fm_has() {
  e=$(fm_end "$1")
  [ -n "$e" ] || return 1
  sed -n "2,$((e - 1))p" "$1" | awk -v k="$2" '
    /^[ \t]/ { next }
    { i = index($0, ":"); if (i > 1) { key = substr($0, 1, i - 1); gsub(/^[ \t]+|[ \t]+$/, "", key); if (key == k) found = 1 } }
    END { exit found ? 0 : 1 }'
}

valid_date() {
  case $1 in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) return 0 ;;
    *) return 1 ;;
  esac
}

prefix=$(g rev-parse --show-prefix)
for f in "$WIKI"/*.md; do
  [ -f "$f" ] || continue
  name=${f##*/}
  if [ -n "$(g check-ignore "$name")" ]; then continue; fi
  if [ -z "$(tr -d ' \t\r\n' < "$f")" ]; then continue; fi

  has_dates=0
  if fm_has "$f" "$CREATED_KEY" && fm_has "$f" "$UPDATED_KEY"; then has_dates=1; fi

  created=$(fm_get "$f" "$CREATED_KEY")
  if [ -z "$created" ]; then
    created=$(g log --follow --diff-filter=A --format=%ad --date=format-local:%Y-%m-%d -- "$name" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | tail -n 1 || true)
    if [ -z "$created" ]; then created=$today; fi
  fi

  # Did the body change since HEAD? A page that is not in HEAD "changes" until it has the dates.
  changed=0
  if g cat-file -e "HEAD:./$name" >/dev/null 2>&1 && [ -n "$(g ls-tree --name-only HEAD -- "$name")" ]; then
    g show "HEAD:./$name" > "$tmp/head.md"
    body_of "$tmp/head.md" "$tmp/head.body"
    body_of "$f" "$tmp/cur.body"
    if ! cmp -s "$tmp/head.body" "$tmp/cur.body"; then changed=1; fi
  elif [ "$has_dates" -eq 0 ]; then
    changed=1
  fi

  if [ "$changed" -eq 1 ]; then
    updated=$today
  else
    updated=$(fm_get "$f" "$UPDATED_KEY")
    if [ -z "$updated" ]; then
      updated=$(g log -1 --format=%ad --date=format-local:%Y-%m-%d -- "$name" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | head -n 1 || true)
      if [ -z "$updated" ]; then updated=$today; fi
    fi
  fi
  if valid_date "$updated" && valid_date "$created" && [ "$updated" != "$created" ]; then
    first=$(printf '%s\n%s\n' "$updated" "$created" | sort | head -n 1)
    if [ "$first" = "$updated" ]; then updated=$created; fi
  fi

  # Rewrite: dates first, other frontmatter lines kept as they are, then the body.
  e=$(fm_end "$f")
  {
    printf -- '---\n%s: %s\n%s: %s\n' "$CREATED_KEY" "$created" "$UPDATED_KEY" "$updated"
    if [ -n "$e" ]; then
      sed -n "2,$((e - 1))p" "$f" | grep -v -E "^($CREATED_KEY|$UPDATED_KEY):" || true
    fi
    printf -- '---\n'
  } > "$tmp/new.md"
  body_of "$f" "$tmp/cur.body"
  cat "$tmp/cur.body" >> "$tmp/new.md"
  if ! cmp -s "$tmp/new.md" "$f"; then
    cat "$tmp/new.md" > "$f"
    echo "${prefix}$name"
  fi
done
