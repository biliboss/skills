---
name: envless
description: "Use um segredo (chave de API, token, senha) num comando sem que o valor passe pela conversa, pelo envless, o cofre da casa (sops + age, um arquivo cifrado por ambiente no git). `envless exec -- <cmd>` injeta o segredo no ambiente do comando; `list` mostra as chaves sem valor; `set` grava pelo stdin; `get` só com `--confirm` e nunca na tela. O `envless mcp` é para cliente sem shell (Cursor, Claude Desktop). Use quando pedirem \"usa a chave do cofre\", \"roda com o token X\", \"guarda esse segredo\", \"põe no envless\", \"qual chave tem no cofre\", \"migra o .env\", \"o script precisa da API key\". Não é a `linear` nem o `gh-app` (essas já leem o token delas por script), nem login OAuth do Claude (esse não vai para o envless)."
metadata:
  version: 0.1.0
---

# envless — o segredo entra no comando, nunca na conversa

O [envless](https://github.com/biliboss/envless) é o nosso cofre: cada ambiente (`dev`, `prod`, `aws`…) é um arquivo cifrado `secrets/<env>.env.enc` dentro de uma **pasta de cofre** (a que tem `.envless/` com `identity.key` e `recipients`). O agente usa o segredo sem nunca ver o valor: ele vai do cofre direto para o ambiente do processo filho, nunca por argv, stdout, log, arquivo do repo, Linear ou conversa.

Onde mora cada credencial da casa e quem a usa está na página `segredos` do wiki do repo da casa (`$CASA_REPO_PRINCIPAL/.wiki/segredos.md`). Procure lá antes de pedir uma chave.

## Passos

1. **Ache o cofre e a chave, sem valor.** Rode a partir da raiz da pasta do cofre:
   ```sh
   cd <pasta-do-cofre>
   ls secrets/                    # os ambientes que existem
   envless list --env=<env>       # as chaves, sem valores
   ```
   - **O envless não sobe de pasta.** Fora da raiz do cofre (num subdiretório, inclusive), `list` volta vazio e `exec` roda o comando **sem os segredos**, os dois com exit 0 e sem aviso. Por isso: sempre `cd` para a raiz, ou `(cd <cofre> && envless exec …)`; se o comando precisa rodar numa subpasta, o `cd` vai dentro do filho: `envless exec -- sh -c 'cd scripts && ./x.sh'`.
   - **Um `--env` que não existe também volta vazio com exit 0.** Lista vazia não prova que a chave falta: confira o `ls secrets/`.
   - Sem `--env`, o ambiente é `dev`.
2. **Use pelo `exec`.** O segredo entra no ambiente do filho; o código de saída do filho volta como o do envless.
   ```sh
   envless exec --env=<env> -- ./script.sh
   envless exec --env=<env> -- sh -c 'curl -sS -H "Authorization: Bearer $TOKEN" https://api…'
   ```
   - **Aspas simples no `sh -c`,** para o `$TOKEN` ser expandido pelo filho, não pelo seu shell (que não tem a variável e passaria vazio).
   - **O comando não pode imprimir o segredo:** nada de `printenv CHAVE`, `echo $CHAVE`, `env`, `set -x` nem `curl -v` (que mostra o header). O que sai do filho cai na conversa.
   - Para conferir que a chave chegou sem ver o valor: `envless exec --env=<env> -- sh -c 'test -n "$CHAVE" && echo presente || echo ausente'` ou `… -- printenv CHAVE | wc -c` (só o tamanho).
   - Um programa que lê o segredo de arquivo (`NOME_FILE=<caminho>`) não precisa do envless: passe o caminho, nunca o conteúdo.
3. **Guardar um segredo novo: pelo stdin.** O valor nunca vai na linha de comando (fica no histórico e no `ps`).
   ```sh
   pbpaste | envless set CHAVE --env=<env>          # o dono copiou o valor
   envless set CHAVE --env=<env> < arquivo          # várias linhas (PEM)
   ```
   - O agente não digita nem gera o valor na conversa. Se é o dono quem tem o segredo, entregue a ele o comando exato para rodar com `!` no prompt (ou num terminal), e confira depois só com `envless list`.
   - Depois de guardar, anote em `.wiki/segredos.md` onde mora e quem usa, nunca o valor.
4. **`get` quase nunca.** Ele imprime o valor e exige `--confirm`. Só quando um programa não aceita variável de ambiente, e sempre para um pipe que não volta à tela (`envless get CHAVE --confirm | pbcopy`). Na dúvida, é `exec`.
5. **Um `.env` em texto puro que apareceu:** `envless migrate .env --env=<env>` cifra, põe o arquivo no `.gitignore` e apaga o original (`--keep` para conferir antes). Repo sem cofre: `envless init` na raiz cria a identidade (`.envless/identity.key`, nunca commitada) e o `recipients` (commitado).

## Shell ou MCP

| Cliente | Use |
|---|---|
| Tem shell (Claude Code, pi, Codex, um script) | o CLI, pelos passos acima. É o padrão |
| Não tem shell (Cursor, Claude Desktop, um app que só fala MCP) | `envless mcp` como servidor stdio na config do cliente, com a pasta do cofre como cwd. Ferramentas: `envs`, `list`, `get` (com `confirm: true`), `set`, `exec` (até 300 s), `init`, `migrate`, `whoami` |

O servidor acha o cofre pelo próprio cwd (o `exec` aceita um `cwd` só para o filho). O `get` do MCP devolve o valor ao modelo e o `set` recebe o valor dele, então os dois põem o segredo na conversa: ali também, use o `exec`, e guarde segredo novo pelo CLI (`set` pelo stdin).

## O que nunca

- **O valor de um segredo nunca vai para a conversa, um arquivo do repo, o wiki, o Linear, um commit ou um log.** Nem num teste: teste pela presença ou pelo tamanho.
- **Não leia nem copie `.envless/identity.key`;** ele é a chave que abre o cofre.
- **Credencial OAuth não vai para o envless** (a do Claude, a do pi): o token se renova a cada uso e a cópia envelhece. O envless é para chave fixa.
- **Tirar o acesso de alguém exige recifrar e trocar o segredo,** porque quem já leu pode ter guardado.
