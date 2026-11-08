#!/usr/bin/env bash
# what: the ag-* tools talk only to the herdr Desktop, through hc (herdr-core): neither tmux nor the `herdr` CLI (another server)
# As ferramentas ag-* falam só com o herdr Desktop, pelo hc (herdr-core): nem tmux nem o `herdr` CLI (outro servidor).
# Só lê: não cria nem fecha terminal na mesa do the owner.
B="${BIN:-$HOME/agents/bin}"

# 1) nenhuma ferramenta ag-* chama o tmux nem o herdr CLI (linhas de comentário não contam)
resto="$(grep -nE 'ag_tmux|TMUX_BIN|AG_TMUX_L|tmux (send|capture|list|load|paste|set|new|kill)|ag_herdr|HERDR_BIN|herdr (pane|agent|tab|workspace)' "$B"/ag-* 2>/dev/null | grep -vE '^[^:]*:[0-9]+:[[:space:]]*#' | head -3)"
[ -z "$resto" ] || { echo "still uses tmux or the herdr CLI:$(printf '%s' "$resto" | head -1)"; exit 1; }

# 2) o hc responde e o ag-lib sabe listar os terminais dele
command -v hc >/dev/null || { echo "no hc in PATH"; exit 1; }
hc ls --json >/dev/null 2>&1 || { echo "hc ls failed (is herdr-core running?)"; exit 1; }
( . "$B/ag-lib.sh"; type ag_terminais >/dev/null 2>&1 ) || { echo "ag-lib.sh has no ag_terminais (the hc terminal list)"; exit 1; }

# 3) ag-pane acha um agente real aberto pelo ag-spawn (o primeiro terminal vivo que roda o claude numa pasta de ~/agents)
agente="$( . "$B/ag-lib.sh"; ag_terminais | awk -F'\t' -v h="$AG_HOME/" '$3 ~ /claude/ && index($4,h)==1 {n=$4; sub(h,"",n); sub("/.*","",n); print n; exit}' )"
[ -n "$agente" ] || { echo "no ~/agents agent open in the Desktop to test ag-pane (open one with ag-spawn)"; exit 1; }
t="$("$B/ag-pane" "$agente" 2>/dev/null)" || { echo "ag-pane '$agente' found nothing"; exit 1; }
case "$t" in t[0-9a-z]*) ;; *) echo "ag-pane returned '$t', expected tN"; exit 1 ;; esac

# 4) ag-read --state devolve um estado conhecido
est="$("$B/ag-read" "$agente" --state 2>/dev/null)"
case "$est" in idle|working|waiting|permission|menu|unsent) ;; *) echo "ag-read --state returned '$est'"; exit 1 ;; esac

echo "hc: '$agente' = $t, state $est"
exit 0
