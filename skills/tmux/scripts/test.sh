#!/usr/bin/env bash
# test.sh: testa os scripts num servidor tmux PRIVADO (socket proprio). Nunca toca o servidor padrao.
# Sai 0 so se todos os casos passam. Nao testa um Claude Code TUI de verdade.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
unset TMUX TMUX_PANE
export TMUX_SOCKET="skilltest-$$"
export LC_ALL="${TEST_LOCALE:-en_US.UTF-8}"
. "$HERE/lib.sh"          # TMUX_BIN e tm (ja com -L)
PANE="$HERE/pane.sh"; WIN="$HERE/win.sh"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/tmux-skilltest.XXXXXX")

SOCK_PATH=""
cleanup() {   # so o socket privado $TMUX_SOCKET
  tm kill-server >/dev/null 2>&1
  [ -n "$SOCK_PATH" ] && case $SOCK_PATH in */skilltest-*) rm -f -- "$SOCK_PATH" ;; esac
}
trap cleanup EXIT

pass=0; failn=0
ok()   { printf 'ok    %s\n' "$1"; pass=$((pass+1)); }
fail() { printf 'FAIL  %s\n' "$1"; [ -n "${2:-}" ] && printf '      %s\n' "$2"; failn=$((failn+1)); }
check() { # check <nome> <comando...>: passa se o comando sai 0
  local name=$1; shift
  if "$@" >/dev/null 2>&1; then ok "$name"; else fail "$name"; fi
}
has() { printf '%s\n' "$1" | grep -qF -- "$2"; }

READER='bash -c '"'"'echo READY; while IFS= read -r l; do printf "GOT:%s\n" "$l"; done'"'"

# --- servidor privado ---
tm -f /dev/null new-session -d -s t -x 120 -y 40 -n first -c "$WORK" 'sleep 600' || { echo "nao subiu o servidor privado"; exit 1; }
SOCK_PATH=$(tm display-message -p -t t: '#{socket_path}')
tm set-option -g remain-on-exit off >/dev/null

# 1. list mostra janela, comando e cwd
out=$("$WIN" list)
real=$(cd "$WORK" && pwd -P)
if has "$out" first && has "$out" sleep && { has "$out" "$WORK" || has "$out" "$real"; }; then ok "list mostra janela/comando/cwd"; else fail "list mostra janela/comando/cwd" "$out"; fi
json=$("$WIN" list --json)
if printf '%s' "$json" | { command -v jq >/dev/null && jq -e 'length>=1 and .[0].window=="first"' >/dev/null || grep -q '"window":"first"'; }; then ok "list --json valido"; else fail "list --json valido" "$json"; fi

# 2. new: nome, comando, %id, nao muda a janela ativa
before=$(tm display-message -p -t t: '#{window_id}')
id_bili=$("$WIN" new bili "$READER" --cwd "$WORK" --session t)
after=$(tm display-message -p -t t: '#{window_id}')
if printf '%s' "$id_bili" | grep -qE '^%[0-9]+$'; then ok "new imprime %id"; else fail "new imprime %id" "$id_bili"; fi
check "new nao muda a janela ativa" [ "$before" = "$after" ]
check "new deu o nome pedido" [ "$(tm display-message -p -t "$id_bili" '#{window_name}')" = bili ]
check "new rodou o comando" "$PANE" wait "$id_bili" --text READY --timeout 5
if "$WIN" new bili 'sleep 1' --session t >/dev/null 2>&1; then fail "new recusa nome repetido"; else ok "new recusa nome repetido"; fi
id_son=$("$WIN" new bili-sonnet "$READER" --session t)
"$PANE" wait "$id_son" --text READY --timeout 5 >/dev/null

# 3. resolucao exata
check "alvo 'bili' resolve para a janela bili (nao bili-sonnet)" [ "$(resolve_pane bili)" = "$id_bili" ]
check "alvo 'bili-sonnet' resolve certo" [ "$(resolve_pane bili-sonnet)" = "$id_son" ]
check "alvo sessao:janela" [ "$(resolve_pane t:bili)" = "$id_bili" ]
check "alvo sessao:janela.pane" [ "$(resolve_pane t:bili.0)" = "$id_bili" ]
check "alvo %id" [ "$(resolve_pane "$id_son")" = "$id_son" ]
err=$("$PANE" read bil 3 2>&1 >/dev/null); rc=$?
if [ $rc -ne 0 ] && has "$err" "bili-sonnet" && has "$err" "%"; then ok "alvo desconhecido (prefixo 'bil') e erro e lista candidatos"; else fail "alvo desconhecido" "rc=$rc $err"; fi
d1=$("$WIN" new dup 'sleep 600' --session t); d2=$("$WIN" new dup 'sleep 600' --session t --allow-duplicate)
err=$("$PANE" read dup 3 2>&1 >/dev/null); rc=$?
if [ $rc -ne 0 ] && has "$err" "ambiguo" && has "$err" "$d1" && has "$err" "$d2"; then ok "alvo ambiguo e erro e lista candidatos"; else fail "alvo ambiguo" "rc=$rc $err"; fi

# 4. read: sem linhas em branco, exatamente as ultimas N
w=$("$WIN" new blank "sh -c 'printf \"a\n\n\nb\n\n   \nc\nd\n\"; exec sleep 600'" --session t)
"$PANE" wait "$w" --text '^d$' --timeout 5 >/dev/null
r=$("$PANE" read blank 3)
check "read devolve so as ultimas 3 sem brancos" [ "$r" = "$(printf 'b\nc\nd')" ]
check "read 100 traz tudo sem brancos" [ "$("$PANE" read blank 100)" = "$(printf 'a\nb\nc\nd')" ]
check "read --keep-blank mantem brancos" [ "$("$PANE" read blank 100 --keep-blank | grep -c '^$')" -gt 0 ]

# 5. send de uma linha
send_case() { # <nome> <texto>
  local name=$1 text=$2
  if "$PANE" send bili "$text" --timeout 5 >/dev/null 2>&1 && "$PANE" wait bili --text "^GOT:$(printf '%s' "$text" | sed 's/[][\.*^$()+?{}|/]/\\&/g')\$" --timeout 5 >/dev/null 2>&1; then ok "$name"; else fail "$name" "$("$PANE" read bili 6 2>&1)"; fi
}
send_case "send linha simples chega inteira" 'ola mundo 123'
check "send -- texto com -n e flag chega" "$PANE" send bili -- '-n --version' --timeout 5
check "  ...e chegou" "$PANE" wait bili --text '^GOT:-n --version$' --timeout 5
send_case "send com aspas, acentos e \$" 'ação "dupla" '"'"'simples'"'"' $HOME `x`'
# 6. multi-linha por paste-buffer
check "send multilinha" "$PANE" send bili $'ml-um\nml-dois\nml-tres' --timeout 5
"$PANE" wait bili --text '^GOT:ml-tres$' --timeout 5 >/dev/null
n=$("$PANE" read bili 100 | grep -oE 'GOT:ml-(um|dois|tres)' | wc -l | tr -d ' ')
check "multilinha chegou como 3 linhas" [ "$n" = 3 ]
# 7. --no-enter
"$PANE" send bili 'parcial-xyz' --no-enter --timeout 5 >/dev/null
check "--no-enter deixa o texto sem enviar" bash -c '! "$0" read bili 100 | grep -q "^GOT:parcial-xyz$"' "$PANE"
check "  ...mas ele esta digitado no pane" bash -c '"$0" read bili 100 | grep -q "parcial-xyz"' "$PANE"
"$PANE" key bili Enter
check "key Enter envia o texto" "$PANE" wait bili --text '^GOT:parcial-xyz$' --timeout 5
# verificacao falha -> 124 sem Enter (pane sem eco)
nw=$("$WIN" new noecho "sh -c 'stty -echo; exec cat >/dev/null'" --session t)
"$PANE" send noecho 'invisivel-qqq' --timeout 1 >/dev/null 2>&1; rc=$?
check "send sem eco: exit 124 e sem Enter" [ "$rc" = 124 ]

# 8. wait
dl=$("$WIN" new delayed "sh -c 'sleep 1; echo LATE_MARK; exec sleep 600'" --session t)
check "wait --text acha texto que aparece depois" "$PANE" wait delayed --text LATE_MARK --timeout 6
"$PANE" wait bili --text NUNCA_APARECE_ZZ --timeout 1 >/dev/null 2>&1; rc=$?
check "wait --text sem aparecer: 124" [ "$rc" = 124 ]
bz=$("$WIN" new busy "sh -c 'i=0; while :; do i=\$((i+1)); echo \$i; sleep 0.2; done'" --session t)
"$PANE" wait busy --idle 1 --timeout 2 >/dev/null 2>&1; rc=$?
check "wait --idle em pane ocupado: 124" [ "$rc" = 124 ]
check "wait --idle em pane quieto: 0" "$PANE" wait first --idle 1 --timeout 6
"$PANE" wait first --timeout 1 >/dev/null 2>&1; rc=$?
check "wait sem --text/--idle: erro" [ "$rc" -ne 0 ]
"$PANE" wait first --text x >/dev/null 2>&1; rc=$?
check "wait sem --timeout: erro" [ "$rc" -ne 0 ]

# 9. rename
"$WIN" rename blank renomeada >/dev/null
check "rename troca o nome da janela" [ "$(tm display-message -p -t "$w" '#{window_name}')" = renomeada ]

# 10. alvo TNN (a opcao @tnn do pane, igualdade exata)
tm set-option -p -t "$w" @tnn T07 >/dev/null
check "alvo T07 resolve o pane que tem @tnn=T07" [ "$("$PANE" read T07 1 >/dev/null 2>&1; echo $?)" = 0 ]
check "alvo T07 e o mesmo pane que o %id" [ "$(. "$HERE/lib.sh"; resolve_pane T07)" = "$(tm display-message -p -t "$w" '#{pane_id}')" ]
"$PANE" read T70 1 >/dev/null 2>&1; rc=$?
check "alvo TNN que ninguem tem e erro (cai na regra do nome e nao acha)" [ "$rc" -ne 0 ]
tm set-option -p -t "$(tm display-message -p -t t:first '#{pane_id}')" @tnn T07 >/dev/null
"$PANE" read T07 1 >/dev/null 2>&1; rc=$?
check "o mesmo TNN em dois panes e erro, nao adivinha" [ "$rc" -ne 0 ]

rm -rf -- "$WORK"
printf '\n%d ok, %d FAIL\n' "$pass" "$failn"
[ "$failn" -eq 0 ]
