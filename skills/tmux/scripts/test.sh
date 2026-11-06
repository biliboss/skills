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


# 11. run.sh: processos longos em sessao nomeada, presa a worktree
RUN="$HERE/run.sh"
export PROCS_DIR="$WORK/procs"
GR="$WORK/gitrepo"; git init -q "$GR" && git -C "$GR" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
git -C "$GR" worktree add -q "$WORK/wt-alpha" -b alpha 2>/dev/null
git -C "$GR" worktree add -q "$WORK/wt-beta" -b beta 2>/dev/null
WA=$(cd "$WORK/wt-alpha" && pwd -P); WB=$(cd "$WORK/wt-beta" && pwd -P)
sopt() { tm show-options -v -t "=$1:" "$2" 2>/dev/null; }
wopt() { tm show-options -wv -t "$1" "$2" 2>/dev/null; }
hasw() { tm list-windows -t "=$1" -F '#{window_name}' 2>/dev/null | grep -qx "$2"; }
nosess() { ! tm has-session -t "=$1" 2>/dev/null; }
nofile_has() { ! grep -q "$1" "$2"; }

before=$(tm display-message -p -t t: '#{window_id}')
"$RUN" start srv --cwd "$WA" -- sh -c 'echo SRV_UP; exec sleep 600' >/dev/null; rc=$?
check "run start sai 0" [ "$rc" = 0 ]
check "run start criou a sessao wt-alpha" tm has-session -t =wt-alpha
check "run start marca @procs=1 e @owner" [ "$(sopt wt-alpha @procs)|$(sopt wt-alpha @owner)" = "1|$WA" ]
check "run start criou a janela srv" [ "$(tm list-windows -t =wt-alpha -F '#{window_name}')" = srv ]
check "run start guarda o log na opcao da janela" [ "$(wopt wt-alpha:srv @log)" = "$PROCS_DIR/wt-alpha/srv.log" ]
check "run start nao muda a janela ativa do servidor" [ "$(tm display-message -p -t t: '#{window_id}')" = "$before" ]
check "run: pane mostra a saida" "$PANE" wait wt-alpha:srv --text SRV_UP --timeout 5
check "run: log tem a saida" grep -q SRV_UP "$PROCS_DIR/wt-alpha/srv.log"
check "run: log tem o cabecalho com data, cwd e cmd" grep -q '^== .*cwd=.*cmd=sh -c' "$PROCS_DIR/wt-alpha/srv.log"
err=$("$RUN" start srv --cwd "$WA" -- sleep 5 2>&1); rc=$?
if [ $rc -ne 0 ] && has "$err" "ja roda"; then ok "run start recusa janela repetida rodando"; else fail "run start recusa janela repetida" "rc=$rc $err"; fi
"$RUN" start srv --cwd "$WA" --restart -- sh -c 'echo SRV_V2; exec sleep 600' >/dev/null; rc=$?
check "run --restart sai 0" [ "$rc" = 0 ]
check "run --restart: janela nova mostra v2" "$PANE" wait wt-alpha:srv --text SRV_V2 --timeout 5
check "run --restart: ainda uma janela so" [ "$(tm list-windows -t =wt-alpha | wc -l | tr -d ' ')" = 1 ]
check "run --restart: log acumula as duas execucoes" [ "$(grep -c '^== ' "$PROCS_DIR/wt-alpha/srv.log")" = 2 ]

# codigo de saida no log e na janela
"$RUN" start boom --cwd "$WA" -- sh -c 'echo antes; exit 7' >/dev/null
check "run: janela mostra o exit" "$PANE" wait wt-alpha:boom --text 'exit=7' --timeout 5
check "run: log termina com exit=7" [ "$("$RUN" log wt-alpha:boom 1)" = exit=7 ]
check "run log N devolve as ultimas N" [ "$("$RUN" log wt-alpha:boom 2 | head -1)" = antes ]
check "run: @state=exited e @exit=7 na janela" [ "$(wopt wt-alpha:boom @state)|$(wopt wt-alpha:boom @exit)" = "exited|7" ]
"$RUN" start boom --cwd "$WA" -- sh -c 'exit 0' >/dev/null; rc=$?
check "run: janela encerrada pode ser reaproveitada sem --restart" [ "$rc" = 0 ]
lsout=$("$RUN" ls)
if has "$lsout" srv && has "$lsout" "$WA" && has "$lsout" running; then ok "run ls lista dono, janela e estado"; else fail "run ls" "$lsout"; fi
lsj=$("$RUN" ls --json)
if command -v jq >/dev/null; then
  check "run ls --json valido (jq)" bash -c 'printf "%s" "$0" | jq -e "map(select(.window==\"srv\" and .owner_exists==true and .state==\"running\"))|length==1"' "$lsj"
else
  check "run ls --json tem a janela srv" bash -c 'printf "%s" "$0" | grep -q "\"window\":\"srv\""' "$lsj"
fi

# --low usa taskpolicy (um falso, que registra os argumentos e tira o -b)
FAKE="$WORK/fake-taskpolicy"
printf '#!/bin/sh\necho "TP:$*" >> "%s/tp.log"\nshift\nexec "$@"\n' "$WORK" > "$FAKE"; chmod +x "$FAKE"
PROCS_TASKPOLICY="$FAKE" "$RUN" start lowjob --cwd "$WA" --low -- sh -c 'echo LOW_RAN' >/dev/null
check "run --low: o comando rodou" "$PANE" wait wt-alpha:lowjob --text LOW_RAN --timeout 5
check "run --low: passou pelo taskpolicy -b" grep -q '^TP:-b sh -c' "$WORK/tp.log"
check "run --low: cabecalho do log diz taskpolicy" grep -q 'low=.*fake-taskpolicy -b' "$PROCS_DIR/wt-alpha/lowjob.log"

# --slot: PROCS_MAX_SLOTS=1 serializa
export PROCS_MAX_SLOTS=1
"$RUN" start s1 --cwd "$WB" --slot -- sh -c 'echo S1_BEGIN; sleep 3; echo S1_END' >/dev/null
"$PANE" wait wt-beta:s1 --text S1_BEGIN --timeout 5 >/dev/null
"$RUN" start s2 --cwd "$WB" --slot -- sh -c 'echo S2_BEGIN' >/dev/null
"$PANE" wait wt-beta:s2 --text 'esperando vaga' --timeout 5 >/dev/null
check "run --slot: o segundo espera enquanto o primeiro roda" nofile_has "^S2_BEGIN" "$PROCS_DIR/wt-beta/s2.log"
check "run --slot: estado waiting" [ "$(wopt wt-beta:s2 @state)" = waiting ]
check "run --slot: o segundo comeca depois do fim do primeiro" "$PANE" wait wt-beta:s2 --text S2_BEGIN --timeout 10
check "run --slot: vagas liberadas no fim" bash -c '! ls "$0"/slots/*.lock >/dev/null 2>&1' "$PROCS_DIR"
# lock velho (pid morto) e retomado
mkdir -p "$PROCS_DIR/slots/1.lock"; echo 999999 > "$PROCS_DIR/slots/1.lock/pid"
"$RUN" start s3 --cwd "$WB" --slot -- sh -c 'echo S3_BEGIN' >/dev/null
check "run --slot: lock de pid morto e reaproveitado" "$PANE" wait wt-beta:s3 --text S3_BEGIN --timeout 6
unset PROCS_MAX_SLOTS

# stop recusa sessao sem tag; stop de janela, de sessao e por dono
tm new-session -d -s untagged -c "$WORK" 'sleep 600'
err=$("$RUN" stop untagged 2>&1); rc=$?
if [ $rc -ne 0 ] && has "$err" recuso && tm has-session -t =untagged 2>/dev/null; then ok "run stop recusa sessao sem tag (e ela segue viva)"; else fail "run stop recusa sessao sem tag" "rc=$rc $err"; fi
"$RUN" stop wt-alpha:srv >/dev/null; rc=$?
if [ $rc = 0 ] && ! hasw wt-alpha srv && hasw wt-alpha boom; then ok "run stop sessao:janela mata so a janela"; else fail "run stop sessao:janela"; fi
"$RUN" stop wt-beta >/dev/null; rc=$?
if [ $rc = 0 ] && nosess wt-beta; then ok "run stop sessao mata a sessao"; else fail "run stop sessao"; fi
"$RUN" stop --owner "$WA" >/dev/null; rc=$?
if [ $rc = 0 ] && nosess wt-alpha; then ok "run stop --owner acha a sessao pelo dono"; else fail "run stop --owner"; fi
check "run log sobrevive a sessao parada" [ -n "$("$RUN" log wt-beta:s2 1)" ]

# reap: dono sumiu mata; sessao sem tag fica
"$RUN" start keep --cwd "$WA" -- sleep 600 >/dev/null
"$RUN" start gone --cwd "$WB" -- sleep 600 >/dev/null
"$RUN" reap >/dev/null
check "run reap com os donos vivos nao mata nada" tm has-session -t =wt-beta
git -C "$GR" worktree remove --force "$WB"
out=$("$RUN" reap --dry-run)
if has "$out" wt-beta && tm has-session -t =wt-beta 2>/dev/null; then ok "run reap --dry-run lista sem matar"; else fail "run reap --dry-run" "$out"; fi
out=$("$RUN" reap)
if has "$out" "matei wt-beta" && nosess wt-beta; then ok "run reap mata a sessao da worktree removida"; else fail "run reap mata a sessao" "$out"; fi
check "run reap deixa a sessao do dono vivo" tm has-session -t =wt-alpha
check "run reap nunca toca sessao sem tag" tm has-session -t =untagged
tm kill-session -t =wt-alpha

# install-reaper com HOME temporario e sem launchctl
FH="$WORK/fakehome"; mkdir -p "$FH"
pl=$(HOME="$FH" "$RUN" install-reaper --print)
check "install-reaper --print: label, intervalo e reap" bash -c 'printf "%s" "$0" | grep -q com.biliboss.procs-reaper && printf "%s" "$0" | grep -q "<integer>60</integer>" && printf "%s" "$0" | grep -q "<string>reap</string>"' "$pl"
check "install-reaper --print: valida com plutil" bash -c 'printf "%s" "$0" | plutil -lint - >/dev/null' "$pl"
HOME="$FH" "$RUN" install-reaper --no-load >/dev/null; HOME="$FH" "$RUN" install-reaper --no-load >/dev/null; rc=$?
check "install-reaper idempotente: grava plist e copia" bash -c '[ "$1" = 0 ] && [ -f "$0/Library/LaunchAgents/com.biliboss.procs-reaper.plist" ] && [ -x "$0/.local/share/procs/bin/run.sh" ]' "$FH" "$rc"
HOME="$FH" "$RUN" uninstall-reaper --no-load >/dev/null
check "uninstall-reaper remove o plist" bash -c '[ ! -e "$0/Library/LaunchAgents/com.biliboss.procs-reaper.plist" ]' "$FH"
check "run --slot: o primeiro terminou com exit=0" grep -q "^exit=0" "$PROCS_DIR/wt-beta/s1.log"

rm -rf -- "$WORK"
printf '\n%d ok, %d FAIL\n' "$pass" "$failn"
[ "$failn" -eq 0 ]
