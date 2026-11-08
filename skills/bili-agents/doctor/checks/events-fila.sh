#!/usr/bin/env bash
# what: the ping hook also appends a JSON line to events.jsonl (PING_PAINEL=0 turns off sending to the panel)
H="$AG_SKILL/scripts/manager-send-back.sh"
t="$(mktemp)"
echo '{"hook_event_name":"Stop","session_id":"abc","last_assistant_message":"feito"}' \
  | AG_EVENTS="$t" PING_PAINEL=0 PING_NOME=teste "$H" >/dev/null 2>&1
linha="$(tail -1 "$t" 2>/dev/null)"; rm -f "$t"
[ -n "$linha" ] || { echo "no line in events.jsonl"; exit 1; }
python3 -I -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["agente"]=="teste" and d["evento"]=="Stop" and int(d["ts"])>0' "$linha" 2>/dev/null \
  || { echo "line without agent, event or ts: $linha"; exit 1; }
echo "events.jsonl receives {ts, agente, evento, texto, sessao}"
