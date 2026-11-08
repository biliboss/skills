#!/bin/sh
# note.sh - create today's journal note and print its path.
# Usage: note.sh [-w WIKI_DIR] [-P PROJECT] [-c CONFIG] [-b] "Title that says what changed"
# The file is <DIARY_DIR>/<YYYY-MM-DD>/<HHMM>-<slug>.md (UTC), starting with `## HH:MM — Title`.
#   -b  read the body from stdin and append it after one blank line. Stdin is read ONLY with -b: agent
#       shells and CI give a stdin that is open but never closes, so reading it implicitly would hang.
# The file ends right after the title line (or after the body), with no trailing blank line. To add the
# paragraph later with `>>`, start it with a blank line: printf '\n%s\n' "text" >> "$path".
# WIKI_DATE / WIKI_TIME override the clock (tests).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
WIKI_ARG='' CFG_ARG='' body=0
while getopts 'w:c:P:b' o; do
  case $o in
    w) WIKI_ARG=$OPTARG ;;
    c) CFG_ARG=$OPTARG ;;
    P) WIKI_PROJECT=$OPTARG ;;
    b) body=1 ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [ $# -lt 1 ]; then
  echo 'usage: note.sh [-w DIR] [-P PROJECT] [-c CONFIG] [-b] "Title"' >&2
  exit 2
fi
title=$1
export WIKI_ARG CFG_ARG WIKI_PROJECT
# shellcheck source=lib.sh
. "$here/lib.sh"
wiki_resolve

day=${WIKI_DATE:-$(date -u +%Y-%m-%d)}
hhmm=${WIKI_TIME:-$(date -u +%H%M)}

# Slug: lowercase, no accents, letters/digits/hyphen, at most 6 words and 50 chars.
# Accents are removed by literal substitutions (a bracket of multibyte letters breaks under LC_ALL=C); combining
# marks (decomposed accents) are two-byte sequences starting with 0xCC or 0xCD.
b1=$(printf '\314')
b2=$(printf '\315')
lo=$(printf '\200')
hi1=$(printf '\277')
hi2=$(printf '\257')
subst="s/${b1}[${lo}-${hi1}]//g;s/${b2}[${lo}-${hi2}]//g"
for pair in á:a à:a â:a ã:a ä:a å:a Á:a À:a Â:a Ã:a Ä:a Å:a é:e è:e ê:e ë:e É:e È:e Ê:e Ë:e \
  í:i ì:i î:i ï:i Í:i Ì:i Î:i Ï:i ó:o ò:o ô:o õ:o ö:o ø:o Ó:o Ò:o Ô:o Õ:o Ö:o Ø:o \
  ú:u ù:u û:u ü:u Ú:u Ù:u Û:u Ü:u ç:c Ç:c ñ:n Ñ:n ý:y ÿ:y Ý:y ß:ss æ:ae Æ:ae œ:oe Œ:oe; do
  subst="$subst;s/${pair%%:*}/${pair#*:}/g"
done
slug=$(printf '%s' "$title" | LC_ALL=C sed -e "$subst" |
  LC_ALL=C tr 'A-Z' 'a-z' | LC_ALL=C tr -c 'a-z0-9' ' ' |
  awk '{ n = (NF < 6 ? NF : 6); s = ""; for (i = 1; i <= n; i++) s = s (i > 1 ? "-" : "") $i; print s }' |
  cut -c1-50 | sed 's/-*$//')
if [ -z "$slug" ]; then slug=note; fi

dir=$DIARY/$day
mkdir -p "$dir"
name=$hhmm-$slug.md
n=2
while [ -e "$dir/$name" ]; do
  name=$hhmm-$slug-$n.md
  n=$((n + 1))
done
path=$dir/$name

hh=$(printf '%s' "$hhmm" | cut -c1-2)
mm=$(printf '%s' "$hhmm" | cut -c3-4)
printf '## %s:%s — %s\n' "$hh" "$mm" "$title" > "$path"
if [ "$body" -eq 1 ]; then
  # Drop leading blank lines; $(...) drops trailing ones. Result: exactly one blank line after the title.
  text=$(awk 'NF { started = 1 } started' || true)
  if [ -n "$text" ]; then printf '\n%s\n' "$text" >> "$path"; fi
fi

if [ ! -f "$DIARY/$day.md" ]; then
  echo "wiki-smith: first note of $day: run day-index.sh, then add the day to $INBOX (last days)" >&2
fi
printf '%s\n' "$path"
