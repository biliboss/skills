#!/bin/sh
# linear.sh <ferramenta> [arg:=json ...]: chama o MCP oficial do Linear pelo mcpc (a sessão @linear, voz do app Bili).
#   Antes de usar uma ferramenta pela primeira vez: linear.sh --ver <ferramenta> (mostra os parâmetros).
#   Lista as ferramentas: linear.sh --lista. Exemplos:
#     linear.sh get_issue id:='"<TIME>-205"'
#     linear.sh save_status_update project:='"Sygnal"' health:='"onTrack"' body:="$(jq -Rs . < corpo.md)"
#   Se o login venceu, ele diz o que o dono precisa rodar (o OAuth abre no navegador).
set -eu
if [ $# -lt 1 ]; then sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; fi
case "$1" in
  --lista) out=$(mcpc @linear tools-list 2>&1) || true ;;
  --ver) out=$(mcpc @linear tools-get "$2" 2>&1) || true ;;
  *) t=$1; shift; out=$(mcpc --json @linear tools-call "$t" "$@" 2>&1) || true ;;
esac
case "$out" in
  *"Authentication required"*|*"unauthorized"*|*"Unauthorized"*)
    mcpc @linear restart >/dev/null 2>&1 || true
    echo "linear.sh: o @linear (o app, por header Bearer) não respondeu nem depois do restart. Não use mcpc login: o navegador aprova a conta do dono e o token sai em nome dele. Refaça pelo passo 8 do roteiro do app (.wiki/linear.md do repo da casa)" >&2
    echo "linear.sh: enquanto isso, o caminho reserva é scripts/lin.sh (GraphQL, mesma voz do app)" >&2
    exit 3 ;;
esac
printf '%s\n' "$out"
