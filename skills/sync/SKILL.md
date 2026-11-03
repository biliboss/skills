---
name: sync
description: Leave every repo the session touched equal to the remote and clean — commit this session's work by path, rebase on origin, lint the .wiki when it is touched, push, and report what is left dirty and whose it is. Manual, run when closing a piece of work. Use when the user says "commit and sync", "sincroniza", "commit e push", "sync all", "deixa tudo igual ao remoto", "não deixa sujo", "fecha e sobe". Not wiki-smith (that writes and commits wiki pages through its own sync.sh) nor delegate-and-review (a PR on a run/* branch): this one closes the session's work straight on the branch it is on.
metadata:
  version: 0.1.0
---

# sync — o repo igual ao remoto, sem sujeira

A regra do Gabriel: **trabalhar direto no `main`, sempre commitar e sincronizar**. Este skill é o fechamento manual dessa regra, repo por repo. O script é `scripts/sync.sh` (nesta pasta); chame pelo caminho do skill instalado.

## 1. Ver o estado de cada repo que a sessão tocou

Liste os repos que a sessão mexeu, não só o da pasta de trabalho (um `src/agents-vps` também conta):

```sh
S=<pasta deste skill>/scripts/sync.sh
$S estado ~/biliboss ~/src/agents-vps
```

Para cada arquivo sujo, decida de quem é:

| O arquivo | O que fazer |
|---|---|
| a sessão escreveu (Write/Edit, ou um comando seu) | entra no commit |
| já estava sujo no começo da sessão, ou outra sessão mexeu (o `git-sync` avisa) | fica fora; só entra se o Gabriel disser "commit all" |
| gerado (`__pycache__/`, `*.pyc`, `node_modules/`) | `.gitignore`, nunca commit |
| vazio ou temporário de outra ferramenta (`*.n`, `*.orig`) | pergunte; não commite nem apague |

## 2. Enviar

Escreva a mensagem num arquivo (assunto + corpo + as linhas de atribuição) e mande só os caminhos seus:

```sh
$S enviar ~/biliboss "$SCRATCH/msg.txt" .wiki/moc-x.md apps/y/server.mjs
```

O script faz, nesta ordem: o lint do `.wiki` (se algum caminho está nele: datas, índice do dia, lint), o `add` por caminho, o commit, o `pull --rebase --autostash` e o `push`. Ele para no primeiro erro e diz qual.

- **Lint vermelho para tudo.** Corrija e rode de novo; nunca encadeie comandos com `;` depois de um lint, porque o commit sai mesmo vermelho.
- **Arquivo compartilhado com linhas de outra sessão** (o `.wiki/index.md`, o índice do dia, o inbox): não passe o arquivo inteiro. Monte a versão com só as suas linhas sobre o `HEAD` e ponha no índice com `git update-index --cacheinfo 100644,$(git hash-object -w <arquivo>),<caminho>`. Depois rode o `enviar` com os outros caminhos (o que está no índice vai junto no commit).
- **`package.json` novo num workspace** (`apps/*`, `libs/*` no biliboss): atualize o lock da raiz com `npm install --package-lock-only --workspace <pasta>` e mande o `package-lock.json` junto. Sem isso, o `npm ci` quebra para todo mundo. Nunca rode `npm i` dentro da pasta do app: ele mexe no lock da raiz sem dizer.
- **Push que contorna a proteção do `main`:** o script avisa. Diga ao Gabriel no relatório.

## 3. Relatar

Uma linha por repo: os commits (hash curto e assunto), se ficou igual ao `origin`, e o que sobrou sujo, dizendo de quem é e por que ficou. Nunca diga "tudo sincronizado" com arquivo da sessão ainda sujo.
