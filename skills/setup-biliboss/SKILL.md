---
name: setup-biliboss
description: "Configure this repo once for the biliboss skills: the .wiki (language, folders, labels in .wiki/wiki.config), where work happens (straight on main, always commit and sync; or run/* branches with a PR) and the main branch name. Run once per repo before the first use of wiki-smith, sync or lp-draft; run again to change a choice. Use when the user says \"setup biliboss\", \"configura o repo para os skills\", \"prepara este repo\", \"onde a gente trabalha neste repo\"."
disable-model-invocation: true
metadata:
  version: 0.2.0
---

# setup-biliboss — o repo pronto para os skills

Os outros skills do plugin pressupõem três escolhas por repo, mais uma opcional. Este skill as faz uma vez e as escreve no próprio repo, para ninguém perguntar de novo.

## 1. Olhar o que já existe

- `git remote -v` e `git symbolic-ref refs/remotes/origin/HEAD`: o repo e o ramo principal.
- `.wiki/` e `.wiki/wiki.config`: já existe wiki? Em que idioma?
- `AGENTS.md` e `CLAUDE.md`: já dizem onde se trabalha (main ou ramo com PR)?
- As regras de proteção do ramo principal: `gh api repos/<dono>/<repo>/rules/branches/<main>` (exigir PR muda a resposta da escolha 2).

Mostre o que achou antes de escrever.

## 2. As escolhas (pergunte só o que faltar)

1. **O wiki:** sim ou não; idioma (`en` ou `pt-BR`). Se sim e não existir, crie a partir dos `templates/` do wiki-smith, com `wiki.config` primeiro.
2. **Onde se trabalha:** `main` (direto no ramo principal, sempre commitar e sincronizar; é o padrão do Gabriel) ou `run` (um ramo `run/<tema>` por trabalho, com PR). Se o ramo principal exige PR e a escolha for `main`, avise que todo push vai contornar a regra.
3. **O ramo principal:** o que o `origin/HEAD` diz.
4. **A trava do handoff (opcional, desligada por padrão):** uma porcentagem de contexto (`HANDOFF_AT=<percent>`, ex.: `60`) a partir da qual o plugin `handoff-guard` do skill `handoff` manda a sessão se passar sozinha, e bloqueia o turno 15 pontos depois. Sem resposta, não escreva a chave. O plugin precisa estar instalado no perfil Hermes (veja `## The guard` no skill `handoff`).

## 3. Escrever

- No `.wiki/wiki.config`, as chaves do wiki-smith (`WIKI_LANG`, `MAIN_BRANCH` e as outras) mais `WORK_MODE=main` ou `WORK_MODE=run` (e `HANDOFF_AT=<percent>`, se a trava foi escolhida).
- Sem wiki: um `.biliboss` na raiz com `WORK_MODE=` e `MAIN_BRANCH=` (e `HANDOFF_AT=`, se escolhida).
- No `AGENTS.md`, uma seção `## Onde se trabalha` com uma frase: a escolha e o skill que fecha o trabalho (`sync`).

Commite só esses arquivos, por caminho, e sincronize com o skill `sync`.
