---
name: git-agente
description: "Make every agent session on the Mac (Claude Code, pi, subagents) commit, push and open PRs as the Bili Clone GitHub App (bili-clone[bot]), never as the owner: the owner's account only approves. The installation token (1 h) is fetched on demand from the VPS over a dedicated ssh key and never written to disk. Scripts: git-credential-bili-mac (git), gh-bot (gh), bili-git-agente (set up a repo or a CLAUDE_CONFIG_DIR, and check). Use before an agent commits or pushes on the Mac, and when the user says \"commita como o bot\", \"push como agente\", \"abre o PR pelo app\", \"o commit saiu com meu nome\", \"configura o git das sessões\", \"liga o bot no Mac\". Not `sync` (that closes the work and syncs with the remote) nor `delegate-and-review` (who does the work): this one is whose name the work goes out under."
metadata:
  version: 0.1.0
---

# git-agente — o agente do Mac escreve no GitHub como o bot

A regra do dono: **agente commita e abre PR como agente, nunca como o dono**; a conta dele só aprova. Na VPS já é assim (o `gh-app` e o `git-credential-bili`). No Mac, o mesmo token de instalação do app Bili Clone (1 h, renovado pela VPS a cada 45 min) chega na hora de cada `git push` ou `gh`: o script pede por ssh, com uma chave só para isso, ao usuário da VPS que só sabe entregar o token (`$CASA_TOKEN_USUARIO@$CASA_TOKEN_HOST`, a role `token-mac` do repo da VPS, `$CASA_REPO_VPS`). O token não vai para disco, para a linha de comando nem para o histórico.

`S` abaixo é `scripts/` desta skill. As chaves vêm do `casa.env`: `CASA_TOKEN_HOST`, `CASA_TOKEN_USUARIO`, `CASA_TOKEN_CHAVE`, `CASA_BOT_NOME`, `CASA_BOT_EMAIL` (e, opcionais, `CASA_BOT_REVIEWER` e `CASA_BIN`).

## Os scripts

| Script | O que faz |
|---|---|
| `git-credential-bili-mac` | o helper do git: pelo dono do repo (`credential.useHttpPath`), pede o token da conta (`biliboss`, `viacorretor`, `mktvirtual`). Só responde a `get` de `https://github.com`; outra conta não ganha token nenhum (o push falha em vez de sair como o dono) |
| `gh-bot <args do gh>` | o `gh` como o bot: a conta do `-R`/`--repo`, do `repos/<dono>/` de um `gh api` ou do `origin`. O `pr create` pede review a `CASA_BOT_REVIEWER` (padrão `biliboss`); o merge (`pr merge`, `.../pulls/N/merge`) é recusado, porque é de uma pessoa |
| `bili-git-agente repo [pasta]` | o git de um repo (`--local`, vale para as worktrees dele) assina como o bot e usa o helper |
| `bili-git-agente sessao <CLAUDE_CONFIG_DIR> [--trava-gh]` | toda sessão daquela pasta do Claude Code: um `git-agente.gitconfig` na pasta (inclui o `~/.gitconfig` do dono e, por cima, o bot) e o `env.GIT_CONFIG_GLOBAL` no `settings.json`. O git do dono fora das sessões não muda. `--trava-gh` deixa o `gh` puro da sessão sem login (`GH_CONFIG_DIR` vazio): nada sai como o dono, e o caminho é o `gh-bot` |
| `bili-git-agente conferir [pasta]` | com quem o git assina, os helpers, o push do `origin` e se o token chega (mostra só `ghs_…`) |

O `bili-git-agente` copia o helper e o `gh-bot` para `CASA_BIN` (padrão `~/.local/bin`), porque o caminho do plugin muda a cada versão: **rode de novo depois de um `claude plugin update`**. O pi (`pi-claude.sh` da skill `pi`) usa o `git-agente.gitconfig` da pasta da conta, se existir.

O que o setup grava (no repo ou no gitconfig da sessão): `user.name`/`user.email` do bot, `commit.gpgsign false` (a chave do dono não assina commit do bot), um helper vazio (zera o `osxkeychain` e o do `gh`, que dariam a conta do dono ou guardariam o token) e depois o helper do bot, `useHttpPath`, e o push de todo `git@github.com:` por https (`pushInsteadOf`). Nas três contas do bot, o fetch também vai por https; nas outras, o fetch por ssh segue.

## Antes de escrever no GitHub

1. `sh S/bili-git-agente conferir`: precisa dizer `commits como: bili-clone[bot]` e `token: ok`. Se avisa, `sh S/bili-git-agente repo .` (ou peça ao dono o `sessao`).
2. Commit antigo com o nome do dono: refaça com `git commit --amend --reset-author` antes do push.
3. Push só em ramo (`run/*`), nunca no `main`: `git push -u origin run/<tema>` (o helper entrega o token).
4. O PR: `gh-bot pr create --title "…" --body "…"`, aberto (não rascunho), pedindo review ao dono. O merge é do dono.
5. Conta fora da lista (o app não está instalado nela, ou a VPS não a entrega): pare e diga ao dono. Não procure outra credencial nem use o `gh` dele.

## Quando falha

- `falta o arquivo …casa.env` ou `falta CASA_…`: preencha a chave a partir do `casa.env.example`.
- `a VPS não entregou um token`: `ssh -i "$CASA_TOKEN_CHAVE" -o IdentitiesOnly=yes "$CASA_TOKEN_USUARIO@$CASA_TOKEN_HOST" biliboss | cut -c1-4` deve dar `ghs_`. `Permission denied`: a chave pública não está no inventory da VPS ou o Ansible não rodou. `conta recusada`: só as três contas valem. Fora da tailnet, a chave não vale.
- `o git não mandou o caminho do repo`: falta `credential.useHttpPath`; rode o `bili-git-agente repo`.

## Ligar no Mac (uma vez, o dono)

```sh
ssh-keygen -t ed25519 -N '' -C bili-token-mac -f ~/.ssh/bili-token-mac
cat ~/.ssh/bili-token-mac.pub    # vai em token_mac_chave_publica no inventory.yml do repo da VPS; aplique a role token-mac
# no casa.env: CASA_TOKEN_HOST, CASA_TOKEN_USUARIO, CASA_TOKEN_CHAVE, CASA_BOT_NOME, CASA_BOT_EMAIL
sh S/bili-git-agente sessao "$CASA_CONTA_PRINCIPAL_DIR" --trava-gh
sh S/bili-git-agente sessao "$CASA_CONTA_SECUNDARIA_DIR" --trava-gh
```

Teste dos scripts (sem rede, com ssh e gh falsos): `sh tests/git-agente.test.sh`.
