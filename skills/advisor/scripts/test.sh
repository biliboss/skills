#!/usr/bin/env bash
# Self-contained test of the advisor scripts, against a throwaway ADVISOR_DIR. The real ~/.local/share/advisor is never
# touched, and nothing is sent to any session.   scripts/test.sh   (exit 0 = all passed)
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
S=$(mktemp -d "${TMPDIR:-/tmp}/advisor-test.XXXXXX")
trap 'rm -rf "$S"' EXIT
export ADVISOR_DIR="$S/dir" ADVISOR_ACTOR=teste
fail=0
ok() { echo "ok    $1"; }
bad() { echo "FAIL  $1"; fail=1; }
check() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }  # check <name> <command that must succeed>
refuses() { if eval "$2" >/dev/null 2>&1; then bad "$1 (should have been refused)"; else ok "$1"; fi; }

echo 'diff com "aspas" e acentuação ção' > "$S/diff.patch"; echo 'SECRET=1' > "$S/.env"

# ask.sh
id=$("$here/ask.sh" ask minha-tarefa --task t --goal 'g "com aspas"' --done d --tried nada --question 'ok?' --resource "$S/diff.patch" 2>/dev/null)
check "ask writes a question.asked line" "jq -e 'select(.id==\"$id\" and .event==\"question.asked\")' $ADVISOR_DIR/context.jsonl"
check "ask copies the resource into resources/<thread>/" "[ -f $ADVISOR_DIR/resources/minha-tarefa/diff.patch ]"
check "ask accepts a resource already in resources/<thread>/ (cp onto itself used to abort)" \
  "$here/ask.sh ask minha-tarefa --task t --goal g --done d --tried t --question q --resource $ADVISOR_DIR/resources/minha-tarefa/diff.patch"
refuses "ask refuses a .env" "$here/ask.sh ask minha-tarefa --task t --goal g --done d --tried t --question q --resource $S/.env"
refuses "ask refuses a missing field" "$here/ask.sh ask minha-tarefa --task t"
refuses "ask refuses a bad thread slug" "$here/ask.sh ask 'Má Thread' --task t --goal g --done d --tried t --question q"
refuses "ask refuses a line over 3500 bytes" "$here/ask.sh ask minha-tarefa --task t --goal g --done d --tried t --question $(head -c 4000 /dev/zero | tr '\0' x)"
"$here/ask.sh" reply minha-tarefa "$id" --verdict corrige --advice 'faça X "assim"' --risk r1 --risk r2 >/dev/null 2>&1
check "reply writes advice.given with the risks" "jq -e 'select(.event==\"advice.given\" and (.value.risks|length)==2)' $ADVISOR_DIR/context.jsonl"
refuses "reply refuses an unknown verdict" "$here/ask.sh reply minha-tarefa $id --verdict talvez --advice a"
check "thread lists the lines" "[ \$($here/ask.sh thread minha-tarefa | grep -c question.asked) -ge 1 ]"

# decide.sh, rate.sh, decisions.sh
refuses "decide refuses a task-kind outside the closed list" "$here/decide.sh t1 --moment plano --called true --reason r --task-kind código"
refuses "decide refuses an unknown moment" "$here/decide.sh t1 --moment cedo --called true --reason r --task-kind codigo"
rec() { "$here/decisions.sh" recent "$@" 2>&1; }
check "no history is CHAME" "rec codigo --moment plano | grep -q CHAME"
call() { # call <thread> <moment> <changed> : a rated call of kind codigo
  "$here/decide.sh" "$1" --moment "$2" --called true --reason r --task-kind codigo >/dev/null
  "$here/rate.sh" rated "$1" "id-$1" --moment "$2" --changed-course "$3" --useful "$3" --note "n $1" >/dev/null
}
call a1 plano false; call a2 plano false
check "2 calls that said segue is still CHAME (PULE needs 3)" "rec codigo --moment plano | grep -q CHAME"
call a3 plano false
check "3 rated calls that said segue is PULE" "rec codigo --moment plano | grep -q PULE"
check "the key is (kind, moment): the same calls do not pool into another moment" "rec codigo --moment terminou | grep -q CHAME"
call a4 plano true
check "a call that changed course is CHAME" "rec codigo --moment plano | grep -q CHAME"
for t in b1 b2 b3; do call $t irreversivel false; done
check "irreversivel never gives PULE" "rec codigo --moment irreversivel | grep -q 'never skips'"
for t in c1 c2 c3; do call $t terminou false; done
"$here/decide.sh" c4 --moment terminou --called false --reason r --task-kind codigo >/dev/null
"$here/rate.sh" missed c4 --moment terminou --what "o teste falhou depois" >/dev/null
check "a missed call is CHAME" "rec codigo --moment terminou | grep -q CHAME"
for t in d1 d2 d3 d4; do "$here/decide.sh" $t --moment travou --called false --reason r --task-kind debug >/dev/null; done
check "a window of only skips is CHAME on purpose" "rec debug --moment travou --last 4 | grep -q CHAME"
check "decisions.jsonl lines stay short" "[ \$(awk '{ if (length(\$0) > m) m = length(\$0) } END { print m }' $ADVISOR_DIR/decisions.jsonl) -le 3500 ]"

[ "$fail" = 0 ] && echo "all passed" || echo "FAILED"
exit "$fail"
