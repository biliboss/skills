#!/usr/bin/env bash
set -eu
S="$(cd "$(dirname "$(dirname "$0")")" && pwd -P)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/config" "$T/state"
cat > "$T/claude" <<'PY'
#!/usr/bin/env python3
import json,os,subprocess,sys,time
from pathlib import Path
args=sys.argv[1:]
assert '-p' in args and '--plugin-dir' in args and '--settings' in args
assert '--continue' not in args and '--bare' not in args and '--resume' not in args
assert not os.environ.get('ANTHROPIC_API_KEY') and not os.environ.get('ANTHROPIC_AUTH_TOKEN')
assert os.environ['CLAUDE_CONFIG_DIR']==os.environ['AG_CLAUDE_CONFIG_DIR']
assert Path.cwd().name.startswith('ag-voice-cwd-')
settings=json.loads(Path(args[args.index('--settings')+1]).read_text())
hook=subprocess.run(settings['hooks']['SessionStart'][0]['hooks'][0]['command'],shell=True,check=True,capture_output=True,text=True)
assert 'qa' in json.loads(hook.stdout)['hookSpecificOutput']['additionalContext']
if os.environ.get('FAKE_TIMEOUT'):time.sleep(1)
response='I verify the request and exercise the behavior before approval.'
if os.environ.get('FAKE_LONG'):response=' '.join(['word']*70)
print(json.dumps({'type':'system','subtype':'hook_response','exit_code':0,'output':hook.stdout}))
if os.environ.get('FAKE_QUOTA'):response="You've hit your weekly limit"
print(json.dumps({'type':'system','subtype':'init','output_style':'Bili','session_id':'fixture'}))
print(json.dumps({'type':'result','result':response,'is_error':False}))
PY
chmod +x "$T/claude"
export AG_CLAUDE_BIN="$T/claude" AG_CLAUDE_CONFIG_DIR="$T/config" AG_VOICE_STATE="$T/state" AG_SKILL="$S" AG_PLUGIN_DIR="$(dirname "$(dirname "$S")")"
export ANTHROPIC_API_KEY=fixture-must-be-removed ANTHROPIC_AUTH_TOKEN=fixture-must-be-removed
"$S/scripts/ag-voice-probe" | grep -q passed
report="$(find "$T/state" -name report.json | head -1)"
jq -e '.probes|length==2 and all(.[];.status=="PASS")' "$report" >/dev/null
if FAKE_LONG=1 "$S/scripts/ag-voice-probe" > "$T/long"; then echo 'accepted long voice'; exit 1; else [ $? -eq 1 ]; fi
if FAKE_TIMEOUT=1 AG_VOICE_TIMEOUT=0.05 "$S/scripts/ag-voice-probe" > "$T/timeout"; then echo 'accepted timeout'; exit 1; else [ $? -eq 3 ]; fi
if FAKE_QUOTA=1 "$S/scripts/ag-voice-probe" > "$T/quota"; then echo 'accepted exhausted subscription'; exit 1; else [ $? -eq 2 ]; fi
# Isolated marketplace selection and unsafe cache fallback.
mkdir -p "$T/config/plugins/marketplaces/custom/skills/bili-agents" "$T/cache-config/plugins/cache/custom/plugin/1/skills"
cp -R "$S/scripts" "$T/config/plugins/marketplaces/custom/skills/bili-agents/"
AG_HOME="$T/home" CLAUDE_CONFIG_DIR="$T/config" AG_MARKETPLACE=custom "$S/scripts/setup" >/dev/null
readlink "$T/home/bin/ag-voice-probe" | grep -q '/marketplaces/custom/'
cp -R "$S" "$T/cache-config/plugins/cache/custom/plugin/1/skills/"
if AG_HOME="$T/unsafe-home" AG_SKILL="$T/cache-config/plugins/cache/custom/plugin/1/skills/bili-agents" CLAUDE_CONFIG_DIR="$T/cache-config" "$S/scripts/setup" > "$T/unsafe" 2>&1; then echo 'accepted unsafe cache links'; exit 1; else [ $? -eq 1 ]; fi
[ ! -e "$T/unsafe-home" ]
printf 'voice probe bounds, fresh invocation, subscription environment, timeout, custom marketplace and unsafe cache refusal verified with fixtures\n'
