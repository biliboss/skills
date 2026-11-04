#!/bin/sh
# Teste dos scripts da skill git-agente, sem rede: um ssh falso no PATH (imprime um token falso da conta pedida e
# anota os argumentos), um gh falso (imprime o GH_TOKEN e os argumentos) e um HOME temporário.
#   sh skills/git-agente/tests/git-agente.test.sh
set -u
AQUI=$(cd "$(dirname "$0")" && pwd)
S="$AQUI/../scripts"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"; mkdir -p "$HOME/.ssh" "$TMP/bin"
unset GIT_CONFIG_GLOBAL GH_TOKEN GH_CONFIG_DIR 2>/dev/null || true
export GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
touch "$HOME/.ssh/bili-token-mac"

cat > "$TMP/bin/ssh" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >> "$SSH_LOG"
[ -n "${SSH_FALHA:-}" ] && { echo "ssh: connect to host vps port 22: Connection refused" >&2; exit 255; }
[ -n "${SSH_LIXO:-}" ] && { printf 'ghs_x\nusername=outro\n'; exit 0; }
for a in "$@"; do conta=$a; done
printf 'ghs_FALSO%s' "$conta"
EOF
cat > "$TMP/bin/gh" <<'EOF'
#!/bin/sh
echo "GH_TOKEN=$GH_TOKEN"
echo "GH_CONFIG_DIR_VAZIO=$([ -z "$(ls -A "$GH_CONFIG_DIR")" ] && echo sim || echo nao)"
echo "ARGS=$*"
EOF
chmod +x "$TMP/bin/ssh" "$TMP/bin/gh"
export PATH="$TMP/bin:$HOME/.local/bin:$PATH" SSH_LOG="$TMP/ssh.log"

CASA_OK="$TMP/casa.env"
cat > "$CASA_OK" <<EOF
CASA_TOKEN_HOST=vps.tailnet
CASA_TOKEN_USUARIO=token-mac
CASA_TOKEN_CHAVE=\$HOME/.ssh/bili-token-mac
CASA_BOT_NOME='bili-clone[bot]'
CASA_BOT_EMAIL='347740005+bili-clone[bot]@users.noreply.github.com'
EOF
export BILIBOSS_CASA="$CASA_OK"

falhas=0; total=0
ok() { total=$((total + 1)); echo "ok   $1"; }
falha() { total=$((total + 1)); falhas=$((falhas + 1)); echo "FALHOU $1"; }
confere() { # <nome> <condição em sh>
  if eval "$2"; then ok "$1"; else falha "$1 ($2)"; fi
}
helper() { # <entrada do protocolo> [args]; saída em $TMP/out, stderr em $TMP/err, código em $rc
  : > "$SSH_LOG"
  printf '%b' "$1" | sh "$S/git-credential-bili-mac" "${2:-get}" > "$TMP/out" 2> "$TMP/err"; rc=$?
}

# --- git-credential-bili-mac ---
helper 'protocol=https\nhost=github.com\npath=biliboss/biliboss.git\n\n'
confere "helper: biliboss pelo dono do repo" '[ $rc = 0 ] && grep -qx "password=ghs_FALSObiliboss" "$TMP/out" && grep -qx "username=x-access-token" "$TMP/out"'
confere "helper: ssh com a chave dedicada, só ela, sem prompt, no token-mac" 'grep -q -- "-i $HOME/.ssh/bili-token-mac -o IdentitiesOnly=yes -o BatchMode=yes" "$SSH_LOG" && grep -q "token-mac@vps.tailnet biliboss$" "$SSH_LOG"'
helper 'protocol=https\nhost=github.com\npath=ViaCorretor/the-viacorretor.git\n\n'
confere "helper: dono em maiúsculas vira viacorretor" 'grep -qx "password=ghs_FALSOviacorretor" "$TMP/out" && grep -q " viacorretor$" "$SSH_LOG"'
helper 'protocol=https\nhost=github.com\npath=mktvirtual/site\n\n'
confere "helper: mktvirtual" 'grep -qx "password=ghs_FALSOmktvirtual" "$TMP/out"'
helper 'protocol=https\nhost=gitlab.com\npath=biliboss/x.git\n\n'
confere "helper: recusa host que não é github.com (sem saída, sem ssh)" '[ $rc = 0 ] && [ ! -s "$TMP/out" ] && [ ! -s "$SSH_LOG" ]'
helper 'protocol=https\nhost=github.com.evil.example\npath=biliboss/x.git\n\n'
confere "helper: recusa github.com.evil.example" '[ ! -s "$TMP/out" ] && [ ! -s "$SSH_LOG" ]'
helper 'protocol=https\nhost=api.github.com\npath=biliboss/x.git\n\n'
confere "helper: recusa api.github.com" '[ ! -s "$TMP/out" ] && [ ! -s "$SSH_LOG" ]'
helper 'protocol=http\nhost=github.com\npath=biliboss/x.git\n\n'
confere "helper: recusa http sem tls" '[ ! -s "$TMP/out" ] && [ ! -s "$SSH_LOG" ]'
helper 'protocol=https\nhost=github.com\npath=devmagic/x.git\n\n'
confere "helper: dono fora da lista não ganha token (e diz por quê)" '[ ! -s "$TMP/out" ] && [ ! -s "$SSH_LOG" ] && grep -q "sem token do bot para .devmagic." "$TMP/err"'
helper 'protocol=https\nhost=github.com\n\n'
confere "helper: sem path diz que falta o useHttpPath" '[ $rc = 1 ] && [ ! -s "$TMP/out" ] && grep -q "useHttpPath" "$TMP/err"'
helper 'protocol=https\nhost=github.com\npath=biliboss/x.git\n\n' store
confere "helper: store não faz nada" '[ $rc = 0 ] && [ ! -s "$TMP/out" ] && [ ! -s "$SSH_LOG" ]'
helper 'protocol=https\nhost=github.com\npath=biliboss/x.git\n\n' erase
confere "helper: erase não faz nada" '[ $rc = 0 ] && [ ! -s "$TMP/out" ] && [ ! -s "$SSH_LOG" ]'
SSH_FALHA=1 helper 'protocol=https\nhost=github.com\npath=biliboss/x.git\n\n'
confere "helper: VPS fora dá erro legível, sem senha (e tenta de novo)" '[ $rc = 1 ] && ! grep -q password "$TMP/out" && grep -q "a VPS não entregou um token" "$TMP/err" && [ "$(wc -l < "$SSH_LOG")" -eq 2 ]'
SSH_LIXO=1 helper 'protocol=https\nhost=github.com\npath=biliboss/x.git\n\n'
confere "helper: resposta com quebra de linha não entra no protocolo" '[ $rc = 1 ] && ! grep -q "username=outro" "$TMP/out"'
BILIBOSS_CASA="$TMP/nao-existe.env" helper 'protocol=https\nhost=github.com\npath=biliboss/x.git\n\n'
confere "helper: sem casa.env, erro dizendo o arquivo" '[ $rc = 1 ] && grep -q "falta o arquivo $TMP/nao-existe.env" "$TMP/err" && [ ! -s "$SSH_LOG" ]'
grep -v CASA_TOKEN_HOST "$CASA_OK" > "$TMP/casa-sem-host.env"
BILIBOSS_CASA="$TMP/casa-sem-host.env" helper 'protocol=https\nhost=github.com\npath=biliboss/x.git\n\n'
confere "helper: sem CASA_TOKEN_HOST, erro dizendo a chave" '[ $rc != 0 ] && grep -q "falta CASA_TOKEN_HOST" "$TMP/err"'
helper 'protocol=https\nhost=github.com\npath=biliboss/x.git\n\n'
confere "helper: nada do token em disco" '! grep -rq ghs_FALSO "$HOME" 2>/dev/null'

# --- gh-bot ---
mkdir -p "$TMP/r1" && git -C "$TMP/r1" init -q && git -C "$TMP/r1" remote add origin git@github.com:ViaCorretor/foo.git
(cd "$TMP/r1" && sh "$S/gh-bot" pr view 3) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "gh-bot: conta pelo origin (ssh, maiúsculas)" '[ $rc = 0 ] && grep -qx "GH_TOKEN=ghs_FALSOviacorretor" "$TMP/out" && grep -qx "GH_CONFIG_DIR_VAZIO=sim" "$TMP/out"'
(cd "$TMP/r1" && sh "$S/gh-bot" issue list -R mktvirtual/site) > "$TMP/out" 2> "$TMP/err"
confere "gh-bot: -R manda mais que o origin" 'grep -qx "GH_TOKEN=ghs_FALSOmktvirtual" "$TMP/out"'
(cd "$TMP" && sh "$S/gh-bot" pr list --repo=https://github.com/biliboss/skills) > "$TMP/out" 2> "$TMP/err"
confere "gh-bot: --repo=URL" 'grep -qx "GH_TOKEN=ghs_FALSObiliboss" "$TMP/out"'
(cd "$TMP" && sh "$S/gh-bot" api repos/biliboss/skills/pulls) > "$TMP/out" 2> "$TMP/err"
confere "gh-bot: gh api repos/<dono>/" 'grep -qx "GH_TOKEN=ghs_FALSObiliboss" "$TMP/out"'
(cd "$TMP/r1" && sh "$S/gh-bot" pr create --title t --body b) > "$TMP/out" 2> "$TMP/err"
confere "gh-bot: pr create pede review ao biliboss" 'grep -qx "ARGS=pr create --reviewer biliboss --title t --body b" "$TMP/out"'
(cd "$TMP/r1" && sh "$S/gh-bot" pr create --reviewer outra --title t) > "$TMP/out" 2> "$TMP/err"
confere "gh-bot: pr create com --reviewer não ganha outro" 'grep -qx "ARGS=pr create --reviewer outra --title t" "$TMP/out"'
(cd "$TMP/r1" && sh "$S/gh-bot" pr merge 3 --squash) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "gh-bot: pr merge recusado (3)" '[ $rc = 3 ] && [ ! -s "$TMP/out" ]'
(cd "$TMP/r1" && sh "$S/gh-bot" api -X PUT repos/viacorretor/foo/pulls/3/merge) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "gh-bot: merge pela API recusado (3)" '[ $rc = 3 ] && [ ! -s "$TMP/out" ]'
(cd "$TMP" && sh "$S/gh-bot" -R devmagic/x pr list) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "gh-bot: conta fora da lista (4), sem gh" '[ $rc = 4 ] && [ ! -s "$TMP/out" ] && grep -q devmagic "$TMP/err"'
(cd "$TMP" && sh "$S/gh-bot" pr list) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "gh-bot: fora de repo e sem -R, diz o que passar" '[ $rc = 4 ] && grep -q "passe -R" "$TMP/err"'
(cd "$TMP/r1" && BILIBOSS_CASA="$TMP/nao-existe.env" sh "$S/gh-bot" pr list) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "gh-bot: sem casa.env, erro dizendo o arquivo" '[ $rc = 1 ] && grep -q "falta o arquivo" "$TMP/err"'

# --- bili-git-agente repo ---
printf '[user]\n\tname = Gabriel\n\temail = gabriel@exemplo\n[commit]\n\tgpgsign = true\n[credential]\n\thelper = "!f() { echo username=gabriel; echo password=SENHA_DO_GABRIEL; }; f"\n' > "$HOME/.gitconfig"
mkdir -p "$TMP/r2" && git -C "$TMP/r2" init -q && git -C "$TMP/r2" remote add origin git@github.com:biliboss/biliboss.git
sh "$S/bili-git-agente" repo "$TMP/r2" > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "repo: roda" '[ $rc = 0 ]'
confere "repo: copia o helper e o gh-bot para ~/.local/bin" '[ -x "$HOME/.local/bin/git-credential-bili-mac" ] && [ -x "$HOME/.local/bin/gh-bot" ]'
confere "repo: assina como o bot" '[ "$(git -C "$TMP/r2" config user.name)" = "bili-clone[bot]" ] && [ "$(git -C "$TMP/r2" config user.email)" = "347740005+bili-clone[bot]@users.noreply.github.com" ]'
confere "repo: sem a assinatura gpg do Gabriel" '[ "$(git -C "$TMP/r2" config --bool commit.gpgsign)" = false ]'
confere "repo: o push do origin ssh vai por https" '[ "$(git -C "$TMP/r2" remote get-url --push origin)" = https://github.com/biliboss/biliboss.git ]'
(cd "$TMP/r2" && git commit -q --allow-empty -m teste) && confere "repo: o commit sai como o bot" '[ "$(git -C "$TMP/r2" log -1 --format="%an <%ae>")" = "bili-clone[bot] <347740005+bili-clone[bot]@users.noreply.github.com>" ]'
: > "$SSH_LOG"
cred=$(printf 'protocol=https\nhost=github.com\npath=biliboss/biliboss.git\n\n' | git -C "$TMP/r2" credential fill 2>/dev/null)
confere "repo: o git credential fill entrega o token do bot, não o do Gabriel" 'printf "%s" "$cred" | grep -qx "password=ghs_FALSObiliboss" && ! printf "%s" "$cred" | grep -q SENHA_DO_GABRIEL'
cred=$(printf 'protocol=https\nhost=github.com\npath=devmagic/x.git\n\n' | git -C "$TMP/r2" credential fill 2>/dev/null); rc=$?
confere "repo: outra conta não cai no helper do Gabriel" '[ $rc != 0 ] && ! printf "%s" "$cred" | grep -q SENHA_DO_GABRIEL'
mkdir -p "$TMP/r3" && git -C "$TMP/r3" init -q && git -C "$TMP/r3" remote add origin git@github.com:devmagic/x.git
sh "$S/bili-git-agente" repo "$TMP/r3" >/dev/null 2>&1
confere "repo: outra conta: fetch segue por ssh, push vai por https (e falha sem token, em vez de sair como o Gabriel)" '[ "$(git -C "$TMP/r3" remote get-url origin)" = git@github.com:devmagic/x.git ] && [ "$(git -C "$TMP/r3" remote get-url --push origin)" = https://github.com/devmagic/x.git ]'
(cd "$TMP/r2" && sh "$S/bili-git-agente" conferir) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "conferir: ok sem imprimir o token" '[ $rc = 0 ] && grep -q "token: ok (ghs_…, da conta biliboss" "$TMP/out" && ! grep -q ghs_FALSO "$TMP/out"'
sh "$S/bili-git-agente" repo "$TMP/r2" >/dev/null 2>&1
confere "repo: rodar de novo não duplica" '[ "$(git -C "$TMP/r2" config --local --get-all credential.https://github.com.helper | wc -l)" -eq 2 ] && [ "$(git -C "$TMP/r2" config --local --get-all url.https://github.com/.pushInsteadOf | wc -l)" -eq 2 ]'

# --- bili-git-agente sessao ---
mkdir -p "$TMP/claude" && echo '{"model":"opus","env":{"FOO":"1"}}' > "$TMP/claude/settings.json"
mkdir -p "$TMP/r4" && git -C "$TMP/r4" init -q && git -C "$TMP/r4" remote add origin https://github.com/mktvirtual/site.git
sh "$S/bili-git-agente" sessao "$TMP/claude" --trava-gh > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "sessao: roda" '[ $rc = 0 ]'
confere "sessao: settings.json ganha o GIT_CONFIG_GLOBAL e o GH_CONFIG_DIR, sem perder o resto" '[ "$(jq -r ".env.GIT_CONFIG_GLOBAL" "$TMP/claude/settings.json")" = "$TMP/claude/git-agente.gitconfig" ] && [ "$(jq -r ".env.GH_CONFIG_DIR" "$TMP/claude/settings.json")" = "$TMP/claude/gh-agente" ] && [ "$(jq -r ".env.FOO + .model" "$TMP/claude/settings.json")" = 1opus ] && [ -f "$TMP/claude/settings.json.antes-git-agente" ]'
G="$TMP/claude/git-agente.gitconfig"
confere "sessao: com o GIT_CONFIG_GLOBAL, o repo sem config própria assina como o bot" '[ "$(GIT_CONFIG_GLOBAL=$G git -C "$TMP/r4" config user.name)" = "bili-clone[bot]" ]'
confere "sessao: fora da sessão o git do Gabriel não muda" '[ "$(git -C "$TMP/r4" config user.name)" = Gabriel ]'
cred=$(printf 'protocol=https\nhost=github.com\npath=mktvirtual/site.git\n\n' | GIT_CONFIG_GLOBAL=$G git -C "$TMP/r4" credential fill 2>/dev/null)
confere "sessao: o helper do Gabriel do ~/.gitconfig incluído é zerado" 'printf "%s" "$cred" | grep -qx "password=ghs_FALSOmktvirtual" && ! printf "%s" "$cred" | grep -q SENHA_DO_GABRIEL'
(cd "$TMP/r4" && GIT_CONFIG_GLOBAL=$G sh "$S/bili-git-agente" conferir) > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "sessao: conferir passa" '[ $rc = 0 ] && grep -q "commits como: bili-clone\[bot\]" "$TMP/out"'
BILIBOSS_CASA="$TMP/nao-existe.env" sh "$S/bili-git-agente" repo "$TMP/r4" > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "bili-git-agente: sem casa.env, erro dizendo o arquivo" '[ $rc = 1 ] && grep -q "falta o arquivo" "$TMP/err"'
grep -v CASA_BOT_EMAIL "$CASA_OK" > "$TMP/casa-sem-email.env"
BILIBOSS_CASA="$TMP/casa-sem-email.env" sh "$S/bili-git-agente" repo "$TMP/r4" > "$TMP/out" 2> "$TMP/err"; rc=$?
confere "bili-git-agente: sem CASA_BOT_EMAIL, erro dizendo a chave" '[ $rc != 0 ] && grep -q "falta CASA_BOT_EMAIL" "$TMP/err"'

echo "$((total - falhas))/$total passaram"
[ "$falhas" = 0 ]
