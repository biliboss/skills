#!/bin/sh
# contas-tokens.sh [--sem-login]: põe no ~/.pi/agent/claude-accounts.json (0600) as contas do cofre do envless,
# para a extensão pi-claude-accounts. Cada chave CLAUDE_TOKEN_<NOME> do cofre (um token de `claude setup-token`)
# vira a conta <nome> (minúsculo). O valor vai do envless ao jq pelo ambiente do filho ($ENV), nunca por argv,
# stdout ou log. Mantém o uso guardado de cada conta, as outras contas e o resto do arquivo.
#   --sem-login: tira a conta do login da pasta (`default`, sem token), que duplica uma das contas do cofre.
# O cofre: $CASA_CLAUDE_COFRE (padrão ~/.cofre-claude), env $CASA_CLAUDE_COFRE_ENV (padrão claude).
# Imprime só os nomes das contas e o tamanho de cada token.
set -eu
CASA="${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"
[ -f "$CASA" ] && . "$CASA"
cofre="${CASA_CLAUDE_COFRE:-$HOME/.cofre-claude}"
envn="${CASA_CLAUDE_COFRE_ENV:-claude}"
store="${PI_CLAUDE_ACCOUNTS_FILE:-$HOME/.pi/agent/claude-accounts.json}"
sem_login=0; [ "${1:-}" = "--sem-login" ] && sem_login=1

[ -d "$cofre/.envless" ] || { echo "contas-tokens: $cofre não é um cofre do envless (falta .envless/)" >&2; exit 1; }
# O envless não sobe de pasta e volta vazio com exit 0 fora da raiz: por isso o cd.
chaves=$(cd "$cofre" && envless list --env="$envn" | grep '^CLAUDE_TOKEN_' || true)
[ -n "$chaves" ] || { echo "contas-tokens: nenhuma chave CLAUDE_TOKEN_* em $cofre (env $envn)" >&2; exit 1; }

mkdir -p "$(dirname "$store")"
# A ordem de uso (a primeira é gasta antes; as outras são reserva) vai no arquivo ao lado, que só o fork do
# biliboss lê e que as instâncias antigas da extensão não reescrevem: $CASA_CLAUDE_PRIORIDADE ("mukutu devmagic").
prio="$(dirname "$store")/claude-accounts-priority.json"
if [ -n "${CASA_CLAUDE_PRIORIDADE:-}" ]; then
  printf '%s\n' $CASA_CLAUDE_PRIORIDADE | jq -R . | jq -s . > "$prio.$$" && mv "$prio.$$" "$prio"
fi
ordem='[]'; [ -f "$prio" ] && ordem=$(jq -c 'if type == "array" then . else [] end' "$prio" 2>/dev/null || echo '[]')
[ -f "$store" ] || printf '{"active":"default","accounts":[{"name":"default"}]}\n' > "$store"
tmp="$store.$$.tmp"
trap 'rm -f "$tmp"' EXIT
(umask 077; cd "$cofre" && CHAVES="$chaves" SEM_LOGIN="$sem_login" envless exec --env="$envn" -- jq '
  . as $old
  | [$ENV.CHAVES | split("\n")[] | select(length > 0)
     | {name: (ltrimstr("CLAUDE_TOKEN_") | ascii_downcase), token: ($ENV[.] | gsub("\\s"; ""))}] as $novas
  | [$novas[].name] as $nomes
  | .accounts = (
      [($old.accounts // [])[]
        | select(.name as $n | $nomes | index($n) | not)
        | select($ENV.SEM_LOGIN != "1" or .token != null)]
      + [$novas[] | . as $c
          | ([($old.accounts // [])[] | select(.name == $c.name) | .usage][0]) as $u
          | if $u then $c + {usage: $u} else $c end])
  | if $ENV.SEM_LOGIN == "1" then .loginRemoved = true else . end
  | ($ordem | map(select(. as $n | [$novas[].name, ($old.accounts // [])[].name] | index($n)))) as $o
  | .accounts |= sort_by(.name as $n | ($o | index($n)) // 1000)
  | if ($o | length) > 0 then .active = $o[0]
    elif ([.accounts[].name] | index($old.active // "")) then .
    else .active = .accounts[0].name end
' --argjson ordem "$ordem" "$store" > "$tmp")
chmod 600 "$tmp"
mv "$tmp" "$store"
trap - EXIT
jq -r '"ativa: \(.active)", (.accounts[] | "  \(.name): \(if .token then "token \(.token | length) caracteres" else "login da pasta" end)")' "$store"
