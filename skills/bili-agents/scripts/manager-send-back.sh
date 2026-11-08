#!/usr/bin/env bash
# manager-send-back.sh: hook de TODO agente do bili-agents. Avisa QUEM PEDIU quando o agente termina, pergunta ou
# precisa de permissão.
#
# Registrado como hook (Stop, Notification e PreToolUse com matcher AskUserQuestion) pelo ag-spawn, que sobe o claude
# com `--settings skills/bili-agents/hooks/ping.json`: nenhum agente precisa de configuração própria. Lê o JSON do hook
# na entrada padrão e escreve uma linha curta no terminal de quem pediu:
#   [sample-project] terminou: <resumo do último texto do agente>
#   [sample-project] pergunta: <texto da pergunta>
#   [sample-project] precisa de você: <mensagem do Notification>
#
# Quem pediu: o terminal que mandou a última mensagem ao agente (ag-send) ou que o abriu (ag-spawn). Fica no rótulo
# `asker` do terminal do agente (`hc label <terminal> asker=tN`). O hook roda dentro do agente, então $HC_TERMINAL_ID é o
# terminal dele: lê o rótulo e entrega a linha com `hc send`. Sem rótulo, cai no gerente de reserva (~/agents/.manager-pane).
# Nunca manda para o próprio terminal.
#
#   manager-send-back.sh --set       registra o terminal atual ($HC_TERMINAL_ID) como o gerente de reserva
#   manager-send-back.sh --show      mostra o gerente de reserva
#   manager-send-back.sh --quem      mostra para quem o ping iria agora (PING_ASKER, rótulo asker, gerente de reserva)
#   manager-send-back.sh --teste     manda um ping de teste
#   echo '{...json do hook...}' | manager-send-back.sh     (uso como hook)
#
# Variáveis: PING_NOME (o nome do agente; sem ele vem da pasta do hook, ~/agents/<nome>), PING_ASKER (força o destino),
# MANAGER_PANE (força o gerente de reserva), MANAGER_PANE_FILE, PING_DRY=1 (só imprime a linha, não envia nem grava),
# PING_PAINEL=0 (grava mas não digita em ninguém), HC_BIN, AG_HOME, AG_EVENTS.
# Nunca bloqueia o agente: sempre sai com 0 e não escreve nada na saída padrão no modo hook.
set -u

AG_HOME="${AG_HOME:-$HOME/agents}"
LOG="$AG_HOME/ping.log"
ULTIMO="$AG_HOME/.ping-ultimo"
PANE_FILE="${MANAGER_PANE_FILE:-$AG_HOME/.manager-pane}"
HC_BIN="${HC_BIN:-$(command -v hc || true)}"

# quem_pediu: imprime o terminal que recebe o ping (vazio se não há ninguém)
quem_pediu() {
  local a="${PING_ASKER:-}"
  if [ -z "$a" ] && [ -n "${HC_TERMINAL_ID:-}" ] && [ -n "$HC_BIN" ]; then
    a="$("$HC_BIN" get "$HC_TERMINAL_ID" 2>/dev/null | jq -r '.labels.asker // empty' 2>/dev/null || true)"
  fi
  [ -n "$a" ] || a="${MANAGER_PANE:-$(command cat "$PANE_FILE" 2>/dev/null || true)}"
  [ "$a" != "${HC_TERMINAL_ID:-}" ] || a=""
  printf '%s' "$a"
}

case "${1:-}" in
  --set)
    if [ -z "${HC_TERMINAL_ID:-}" ]; then echo "manager-send-back: sem \$HC_TERMINAL_ID; rode isto dentro do terminal do gerente (no herdr Desktop)" >&2; exit 1; fi
    printf '%s\n' "$HC_TERMINAL_ID" > "$PANE_FILE"
    echo "gerente de reserva: $HC_TERMINAL_ID (em $PANE_FILE)"
    exit 0 ;;
  --show)
    command cat "$PANE_FILE" 2>/dev/null || echo "nenhum gerente registrado"
    exit 0 ;;
  --quem)
    quem_pediu; echo
    exit 0 ;;
  --teste)
    ENTRADA='{"hook_event_name":"Notification","message":"teste do manager-send-back"}' ;;
  *)
    ENTRADA="$(command cat 2>/dev/null || true)" ;;
esac

# o nome do agente: PING_NOME, ou a pasta do hook (~/agents/<nome>/...), ou a última parte do cwd
NOME="${PING_NOME:-}"
if [ -z "$NOME" ]; then
  CWD="$(printf '%s' "$ENTRADA" | jq -r '.cwd // empty' 2>/dev/null || true)"
  case "$CWD" in "$AG_HOME"/*) NOME="${CWD#"$AG_HOME"/}"; NOME="${NOME%%/*}" ;; esac
  [ -n "$NOME" ] || NOME="${CWD##*/}"
  [ -n "$NOME" ] || NOME="agente"
fi

PY='
import json, os, re, sys

def limpa(s, n=200):
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"

def ultimo_texto(caminho):
    try:
        tam = os.path.getsize(caminho)
        with open(caminho, "rb") as f:
            f.seek(max(0, tam - 400000))
            linhas = f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return ""
    for linha in reversed(linhas):
        try:
            d = json.loads(linha)
        except Exception:
            continue
        if d.get("type") != "assistant":
            continue
        c = (d.get("message") or {}).get("content")
        if isinstance(c, str) and c.strip():
            return c
        for b in (c or []) if isinstance(c, list) else []:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip():
                return b["text"]
    return ""

try:
    d = json.loads(sys.stdin.read() or "{}", strict=False)
except Exception:
    d = {}

ev = d.get("hook_event_name") or ""
if ev == "Stop":
    if d.get("stop_hook_active"):
        sys.exit(0)
    t = d.get("last_assistant_message") or ultimo_texto(d.get("transcript_path") or "")
    msg = "finished: " + limpa(t) if t else "finished"
elif ev == "PreToolUse":
    if d.get("tool_name") != "AskUserQuestion":
        sys.exit(0)
    qs = (d.get("tool_input") or {}).get("questions") or []
    q = qs[0].get("question") if qs and isinstance(qs[0], dict) else ""
    msg = "question: " + limpa(q) if q else "question"
elif ev == "Notification":
    msg = "needs you: " + limpa(d.get("message") or d.get("notification_type") or "")
elif ev:
    msg = limpa(ev) + ": " + limpa(d.get("message") or d.get("tool_name") or "")
else:
    sys.exit(0)  # entrada que não é JSON de hook: não manda nada
print(msg)
'

MSG="$(printf '%s' "$ENTRADA" | python3 -I -c "$PY" 2>/dev/null || true)"
[ -n "$MSG" ] || exit 0
LINHA="[$NOME] $MSG"

if [ "${PING_DRY:-}" = "1" ]; then
  printf '%s\n' "$LINHA"
  exit 0
fi

# fila de eventos em JSON (uma linha por evento), lida pelo ag-wait; AG_EVENTS troca o arquivo
EV_ARQ="${AG_EVENTS:-$AG_HOME/events.jsonl}"
EV_INFO="$(printf '%s' "$ENTRADA" | python3 -I -c 'import json,sys; d=json.loads(sys.stdin.read() or "{}", strict=False); print(str(d.get("hook_event_name",""))+"\t"+str(d.get("session_id","")))' 2>/dev/null || true)"
python3 -I -c 'import json,sys,time; print(json.dumps({"ts":int(time.time()),"agente":sys.argv[1],"evento":sys.argv[2],"sessao":sys.argv[3],"texto":sys.argv[4]}, ensure_ascii=False))' \
  "$NOME" "${EV_INFO%%$'\t'*}" "${EV_INFO#*$'\t'}" "$MSG" >> "$EV_ARQ" 2>/dev/null || true

# não repete o mesmo ping em 5 s
AGORA="$(date +%s)"
CHAVE="$(printf '%s' "$LINHA" | cksum | cut -d' ' -f1)"
if [ -f "$ULTIMO" ]; then
  read -r T0 C0 < "$ULTIMO" 2>/dev/null || true
  if [ "${C0:-}" = "$CHAVE" ] && [ $(( AGORA - ${T0:-0} )) -lt 5 ]; then exit 0; fi
fi
printf '%s %s\n' "$AGORA" "$CHAVE" > "$ULTIMO" 2>/dev/null || true

DEST="$(quem_pediu)"
printf '%s %s -> %s\n' "$(date '+%F %T')" "$LINHA" "${DEST:-ninguém}" >> "$LOG" 2>/dev/null || true

[ "${PING_PAINEL:-1}" = "0" ] && exit 0
[ -n "$DEST" ] && [ -n "$HC_BIN" ] || exit 0
"$HC_BIN" get "$DEST" >/dev/null 2>&1 || exit 0

# em segundo plano, para o hook não atrasar o agente; o hc send cola o texto e dá o Enter depois de uma pausa
( "$HC_BIN" send "$DEST" "$LINHA" ) >/dev/null 2>&1 &
disown 2>/dev/null || true
exit 0
