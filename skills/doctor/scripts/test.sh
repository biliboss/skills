#!/usr/bin/env bash
# Exercises doctor.py on two temp fixture repos: a healthy python one and a broken one.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DOC="$HERE/doctor.py"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/doctor-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "ok   $1"; }
bad() { fail=$((fail+1)); echo "FAIL $1"; }
check() { # name, condition-exit-code
  if [ "$2" -eq 0 ]; then ok "$1"; else bad "$1"; fi
}

# ---- healthy fixture: README, .wiki, AGENTS.md, pyproject with a CLI, a passing test, a project doctor
H="$TMP/healthy"; mkdir -p "$H/.wiki" "$H/tests" "$H/scripts"
cat > "$H/README.md" <<'EOF'
# healthy
EOF
echo "# wiki" > "$H/.wiki/README.md"
echo "# agents" > "$H/AGENTS.md"
cat > "$H/pyproject.toml" <<'EOF'
[project]
name = "healthy"
version = "0.1.0"
EOF
cat > "$H/main.py" <<'EOF'
import logging
logging.getLogger("healthy").info("hi")
def health(): return "/health"
EOF
cat > "$H/scripts/test.sh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$H/scripts/doctor" <<'EOF'
#!/usr/bin/env bash
echo "warn behavior queue-depth: 3 jobs stuck -> restart the worker"
echo '{"dimension":"observability","check":"heartbeat","status":"ok","evidence":"fresh","action":""}'
exit 0
EOF
chmod +x "$H/scripts/test.sh" "$H/scripts/doctor"
git -C "$H" init -q && git -C "$H" add -A && git -C "$H" -c user.email=t@t -c user.name=t commit -qm init

out="$("$DOC" "$H" --run-tests --verbose 2>"$TMP/err")"; rc=$?
check "healthy: exit 0" $([ $rc -eq 0 ] && echo 0 || echo 1)
echo "$out" | grep -q '^ok behavior tests: `bash scripts/test.sh` passed'; check "healthy: tests run and pass" $?
echo "$out" | grep -q '^ok architecture readme'; check "healthy: readme ok (verbose)" $?
echo "$out" | grep -q 'scripts/doctor:queue-depth: 3 jobs stuck -> restart the worker'; check "healthy: project doctor text finding merged" $?
echo "$out" | grep -q 'scripts/doctor:heartbeat'; check "healthy: project doctor json finding merged" $?
grep -q '^summary healthy:' "$TMP/err" || echo "$out" | grep -q '^summary healthy:'; check "healthy: summary line" $?

out="$("$DOC" "$H" --no-project-doctor 2>&1)"; rc=$?
echo "$out" | grep -q '^ok '; [ $? -ne 0 ]; check "default hides ok findings" $?
echo "$out" | grep -q '^warn behavior tests: .*not run'; check "tests not run -> warn" $?

# ---- --json: one parseable object per line
"$DOC" "$H" --json --no-project-doctor 2>/dev/null > "$TMP/j.out"
bad_lines=0
while IFS= read -r l; do printf '%s' "$l" | grep -q '"status": "' || bad_lines=$((bad_lines+1)); done < "$TMP/j.out"
check "json: every line is a finding" $([ $bad_lines -eq 0 ] && [ -s "$TMP/j.out" ] && echo 0 || echo 1)

# ---- broken fixture: no README, failing tests, stale lock
B="$TMP/broken"; mkdir -p "$B"
cat > "$B/pyproject.toml" <<'EOF'
[project]
name = "broken"
version = "0.1.0"
EOF
echo "" > "$B/uv.lock"; touch -t 202001010000 "$B/uv.lock"
mkdir -p "$B/scripts"; printf '#!/usr/bin/env bash\necho boom >&2\nexit 3\n' > "$B/scripts/test.sh"; chmod +x "$B/scripts/test.sh"
out="$("$DOC" "$B" --run-tests --no-project-doctor 2>&1)"; rc=$?
check "broken: exit 1" $([ $rc -eq 1 ] && echo 0 || echo 1)
echo "$out" | grep -q '^fail architecture readme'; check "broken: missing README is fail" $?
echo "$out" | grep -q '^drift environment python-lock: .* -> uv lock'; check "broken: stale lock is drift with action" $?
echo "$out" | grep -q '^fail behavior tests: .*exit 3.*boom'; check "broken: failing tests are fail with evidence" $?

# ---- central wiki: no .wiki/ or docs/, but a $WIKI_HOME project claims this repo's origin
W="$TMP/wiki-home"; mkdir -p "$W/proj" && printf 'REPO=owner/name\n' > "$W/proj/wiki.config"
C="$TMP/central"; mkdir -p "$C" && echo "# c" > "$C/README.md"
git -C "$C" init -q && git -C "$C" remote add origin git@github.com:owner/name.git
out="$(WIKI_HOME="$W" "$DOC" "$C" --verbose --no-project-doctor 2>&1)"
echo "$out" | grep -q '^ok architecture wiki-or-docs: .*WIKI_HOME/proj'; check "central wiki: REPO= match passes" $?
out="$(WIKI_HOME="$TMP/no-such-home" "$DOC" "$C" --verbose --no-project-doctor 2>&1)"
echo "$out" | grep -q '^warn architecture wiki-or-docs'; check "central wiki: no match still warns" $?

# ---- cannot run
"$DOC" "$TMP/does-not-exist" >/dev/null 2>&1; rc=$?
check "missing dir: exit 2" $([ $rc -eq 2 ] && echo 0 || echo 1)

echo "---"; echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
