#!/usr/bin/env bash
# check.sh - verify the herdr skill: requirements, logging, script hygiene, dry runs, safety refusals and boundaries.
# Usage: check.sh [-h]
# Never changes the window: it only runs -h, -n (dry runs), refusals without --yes, bash -n, and read commands.
# Env: LOGGING_EMIT (or BILIBOSS_ENV) is resolved as the scripts do; LOGGING_FILE is not written (logging's own
#   check uses a temp file).
# stdout: one "ok" or "FAIL" line per check. Exit: 0 all pass; 1 something failed; 2 usage.
. "$(dirname "$0")/lib.sh"
hl_parse "$@"; set -- "${ARGS[@]}"
[ $# -eq 0 ] || hl_usage_err "takes no arguments"
fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }
sh=${BASH:-bash}
root=$(cd "$HERE/.." && pwd)

for c in bash herdr-app hc jq; do if command -v "$c" >/dev/null 2>&1; then ok "requirement: $c"; else bad "requirement missing: $c"; fi; done

if hl_discover 2>/dev/null; then
  ok "LOGGING_EMIT resolves: $LOGGING_EMIT"
  if "$(dirname "$LOGGING_EMIT")/check.sh" >/dev/null 2>&1; then ok "logging check.sh passes"; else bad "logging check.sh fails"; fi
else bad "LOGGING_EMIT does not resolve to an executable (set it in the environment or in \${BILIBOSS_ENV:-\$HOME/.config/biliboss/.env})"; fi

scripts=$(cd "$HERE" && ls *.sh)
for s in $scripts; do
  if [ -x "$HERE/$s" ]; then :; else bad "not executable: $s"; fi
  if "$sh" -n "$HERE/$s" 2>/dev/null; then :; else bad "bash -n fails: $s"; fi
  if [ "$s" != lib.sh ]; then
    if "$sh" "$HERE/$s" -h 2>/dev/null | grep -q .; then :; else bad "-h prints nothing: $s"; fi
  fi
done
ok "scripts: executable, bash -n and -h checked"

# State-changing scripts: -n must print a command. Targets are made-up ids, and -n never runs anything.
while IFS='|' read -r s a; do
  [ -n "$s" ] || continue
  out=$(eval "\"$sh\" \"$HERE/$s\" -n $a" 2>/dev/null </dev/null); rc=$?
  if [ $rc -eq 0 ] && [ -n "$out" ]; then ok "-n prints a command: $s"; else bad "-n failed (exit $rc): $s $a"; fi
done <<'CASES'
space-new.sh|--name check-dry
tab-new.sh|--name check-dry --task hello
split.sh|--place down
focus.sh|pane p-check-dry
rename.sh|tab tb-check-dry newname
zoom.sh|
settle.sh|--undo
layout.sh|--next
spawn.sh|--name check-dry -- cat
send.sh|t-check-dry hello
keys.sh|t-check-dry enter
interrupt.sh|t-check-dry
label.sh|t-check-dry a=b
run.sh|--name check-dry -- true
remote-exec.sh|--on m-check -- true
remote-file.sh|write --on m-check /x
remote-file.sh|edit --on m-check --old a --new b /x
close.sh|--yes tab tb-check-dry
kill.sh|--yes t-check-dry
feedback.sh|hello
do.sh|space.new --name check-dry
CASES

"$sh" "$HERE/close.sh" tab tb-check-dry >/dev/null 2>&1; rc=$?
if [ $rc -eq 2 ]; then ok "close.sh without --yes exits 2"; else bad "close.sh without --yes exited $rc"; fi
"$sh" "$HERE/kill.sh" t-check-dry >/dev/null 2>&1; rc=$?
if [ $rc -eq 2 ]; then ok "kill.sh without --yes exits 2"; else bad "kill.sh without --yes exited $rc"; fi

# Boundaries: the skill only knows Herdr Desktop and the logging dependency. Patterns are assembled so this file passes.
old="herdr"; hits=$(grep -rnE "(^|[^A-Za-z.-])${old} (pane|agent|tab|workspace|wait|server|integration)|~/(agents|biliboss)|HOME/(agents|biliboss)|\\bag-[a-z]+|\\basker\\b|\\bpings?\\b|casa\\.env|duplo-local|prime-agent|\\btmux\\b|impeccable" "$root" --exclude=check.sh || true)
for d in "$root"/../*/; do n=$(basename "$d"); case $n in herdr|logging) continue;; esac
  h=$(grep -rnE "skills/$n([^a-z-]|$)|\`$n\` skill" "$root" --exclude=check.sh || true); hits="$hits$h"; done
if [ -z "$hits" ]; then ok "no forbidden references"; else bad "forbidden references:"; echo "$hits"; fi
exit $fail
