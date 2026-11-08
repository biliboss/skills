#!/usr/bin/env bash
# category: Doctor
# what: everything the doctor prints is English: no Portuguese in the messages of any check, except the words listed in doctor/pt-ok.txt
# fix: translate the echo/printf messages of the listed checks to English (messages only; keep the logic). If a Portuguese word is a functional literal (the real output of another tool, or a UI label a check greps for), add it to doctor/pt-ok.txt
D="${AG_DOCTOR:-$AG_SKILL/doctor}"
command -v perl >/dev/null || { echo "perl is needed to scan for accents"; exit 1; }
export PT_OK="$D/pt-ok.txt"
bad=""
for f in "$D"/checks/*.sh "$D"/pendentes/*.sh; do
  [ -f "$f" ] || continue
  [ "$(basename "$f")" = "doctor-english.sh" ] && continue   # its own pattern holds the accents it looks for
  if perl -Mutf8 -CSD -e '
      my @ok; if (open(my $h, "<:utf8", $ENV{PT_OK})) { @ok = grep { length } map { chomp; $_ } <$h>; }
      open(my $in, "<:utf8", $ARGV[0]) or exit 0;
      while (<$in>) {
        next if /^\s*#/;
        next unless /(echo|printf)/;
        my $l = $_; $l =~ s/\Q$_\E//g for @ok;
        exit 1 if $l =~ /[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]/;
      }
      exit 0;' "$f"; then :; else bad="$bad $(basename "$f" .sh)"; fi
done
[ -z "$bad" ] || { echo "Portuguese in messages:$(printf '%s' "$bad" | cut -c1-150)"; exit 1; }
echo "all check messages are English (functional literals are listed in pt-ok.txt)"
