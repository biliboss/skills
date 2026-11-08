---
name: sync
description: Leave every repo the session touched equal to the remote and clean — commit this session's work by path, rebase on origin, lint the project's wiki (skill `wiki`) when it is touched, push, and report what is left dirty and whose it is. Manual, run when closing a piece of work. Use when the user says "commit and sync", "sincroniza", "commit e push", "sync all", "deixa tudo igual ao remoto", "não deixa sujo", "fecha e sobe". Not wiki (that writes and commits wiki pages through its own sync.sh) nor delegate-and-review (a PR on a run/* branch); this one closes the session's work straight on the branch it is on.
metadata:
  version: 0.1.5
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
| já estava sujo, ou outra sessão mexeu | também entra: é trabalho do Gabriel. Rode o lint, leia o diff e faça **um commit separado**, com o assunto do que aquilo é, para não misturar com o seu |
| gerado (`__pycache__/`, `*.pyc`, `node_modules/`) | `.gitignore`, nunca commit |
| vazio ou temporário de outra ferramenta (`*.n`, `*.orig`) | pergunte; não commite nem apague |

## 2. Enviar

Escreva a mensagem num arquivo (assunto + corpo + as linhas de atribuição) e mande só os caminhos seus:

```sh
$S enviar ~/biliboss "$SCRATCH/msg.txt" .wiki/moc-x.md apps/y/server.mjs
```

O script faz, nesta ordem: o lint da wiki do projeto (skill `wiki`) (se algum caminho está nele e o wiki tem `$WIKI_HOME/<projeto>/wiki.config`: datas, índice do dia, lint; um wiki sem `wiki.config` tem outras regras e fica como está), o `add` por caminho, o commit, o `pull --rebase --autostash` e o `push`. Ele para no primeiro erro e diz qual.

- **Lint vermelho para tudo.** Corrija e rode de novo; nunca encadeie comandos com `;` depois de um lint, porque o commit sai mesmo vermelho.
- **Arquivo compartilhado com linhas de outra sessão** (o `$WIKI_HOME/<projeto>/index.md`, o índice do dia, o inbox): não passe o arquivo inteiro. Monte a versão com só as suas linhas sobre o `HEAD` e ponha no índice com `git update-index --cacheinfo 100644,$(git hash-object -w <arquivo>),<caminho>`. Depois rode o `enviar` com os outros caminhos (o que está no índice vai junto no commit).
- **`package.json` novo num workspace** (`apps/*`, `libs/*` no biliboss): atualize o lock da raiz com `npm install --package-lock-only --workspace <pasta>` e mande o `package-lock.json` junto. Sem isso, o `npm ci` quebra para todo mundo. Nunca rode `npm i` dentro da pasta do app: ele mexe no lock da raiz sem dizer.
- **`pull --rebase` aborta com "untracked working tree files would be overwritten"** (outra sessão commitou no remoto um arquivo que aqui ainda está solto): copie os arquivos listados para o scratch, apague-os, rode o pull de novo e devolva só os que diferiam do `origin/main` (compare com `git show origin/main:<caminho>`); o igual já veio pelo pull. Se o autostash voltar com conflito (`UU`), resolva o arquivo guardando as duas partes, `git restore --staged .` para devolver o resto como estava, e deixe o `stash@{0}` (o autostash não é descartado quando há conflito) — avise no relatório. Só depois de o arquivo resolvido conter as duas partes e o resto estar de volta no checkout, `git stash drop` é seguro (o stash já foi todo aplicado). Nunca `git stash drop` um stash que voltou com conflito antes de aplicar o que ele guarda em outro lugar: ele carrega as edições soltas de outra sessão. Se um foi descartado, ele ainda existe como commit solto: `git fsck --no-reflog | awk '/dangling commit/{print $3}'`, ache o de assunto `WIP on <ramo>: <sha>` (`git log -1 --format=%s <c>`), guarde num ramo (`git branch rescue/<tema> <c>`) e aplique com `git diff <c>^1 <c> -- <caminhos>`.
- **Clone principal que outras sessões editam sem commit** (o `~/src/skills`, onde o aprendizado automático grava SKILL.md soltos): antes do pull, salve `git diff > $SCRATCH/<repo>-solto-$(date +%H%M).patch`, rode `pull --rebase --autostash` e, na mesma hora, leve as edições soltas a um PR próprio (ramo, versão e CHANGELOG de cada skill). Edição solta deixada ali bloqueia o próximo pull, e um processo que importa código desse clone (o dev-console) fica rodando a versão velha.
- **Commit só da wiki do projeto (skill `wiki`) com o checkout sujo ou divergente** (outra sessão trabalhando nele): publique de uma cópia limpa, `git worktree add --detach $SCRATCH/wt-<tema> origin/main`, aplique só os seus arquivos lá, commit e `gh-app push origin HEAD:main`, depois `git worktree remove --force`. Copie o arquivo final de volta para o checkout principal, para os dois ficarem iguais.
- **Um arquivo só do clone principal sujo vira PR por worktree limpo**: `git worktree add -b run/<x> <dir> origin/main`, `cp` só o seu arquivo para lá, commit, `gh-app push`, `gh-app pr create`, `gh pr merge --squash --delete-branch`, `git worktree remove --force`, `branch -D` e `pull --rebase --autostash` no clone. Nunca `git add` no clone principal: ele carrega edições soltas de outras sessões que iriam junto.
- **PR que dá conflito no `plugin.json` (versão e descrição que todo PR mexe):** nunca rebase + force push; mescle o main no ramo do PR (`git merge origin/main`), resolva e empurre normal. Num merge, `:2` é o ramo do PR e `:3` é o main (o inverso do rebase): fica a descrição do main mais a frase que o PR acrescentou, versão = maior das duas com minor +1, listas unidas. Confira `gh pr view --json mergeable` antes do `gh pr merge`; se o main andou no meio (outro merge), repita. Se o ramo do PR já tem worktree ("already used by worktree"), trabalhe nele em vez de criar outro. Um script que remove o worktree no fim deve parar antes se o PR não ficou `MERGED`.
- **Merge quando o Gabriel pede ("merge all", "faz o merge")**: o `gh-app` recusa merge de propósito (o merge é de uma pessoa); o pedido explícito dele autoriza `gh pr merge <n> --squash` com o `gh` comum, logado na conta dele. Sem esse pedido, o relato diz que o merge é dele, com o link do PR.
- **Ramo de worktree criado com `git worktree add -b <x> <dir> origin/main` herda `origin/main` como upstream**: `gh-app push` sozinho empurraria para o `main`. Empurre sempre com `gh-app push -u origin <x>`.
- **`gh pr merge --delete-branch` falha ao apagar o ramo local quando um worktree ainda o usa** (o merge no remoto já aconteceu): rode `git worktree remove --force <dir>` e `git branch -D <x>` depois; confira `gh pr view <n> --json state` = `MERGED` antes de concluir.
- **Depois de juntar mudança de skill ou plugin, atualize os instalados:** `claude plugin marketplace update biliboss` e `claude plugin update biliboss-skills@biliboss`, também para cada conta (`CLAUDE_CONFIG_DIR=~/.claude-<conta>`); `hermes -p bili plugins update --yes` para os plugins do Hermes (sem `--yes`, fora de um terminal interativo ele não atualiza) (as skills o Hermes lê do clone, então basta o pull). As sessões do Claude Code só pegam a versão nova ao reiniciar: diga isso no relatório.
- **Push que contorna a proteção do `main`:** o script avisa. Diga ao Gabriel no relatório.
- **Repo em que o agente não pode empurrar no `main`** (o gh-app recusa; no biliboss só a wiki do projeto (skill `wiki`) vai direto): um commit que fica só no `main` local se perde quando outra sessão alinha o checkout com o `origin`. Na mesma hora, ponha o commit num ramo (`git branch -f run/<tema> <sha>`), empurre esse ramo e abra o PR. Nunca deixe trabalho só no `main` local para depois.

## 3. Relatar

Uma linha por repo: os commits (hash curto e assunto) e se ficou igual ao `origin`. O normal é não sobrar nada sujo; se sobrar (um temporário que você perguntou), diga o quê e por quê. Nunca diga "tudo sincronizado" com arquivo da sessão ainda sujo.
