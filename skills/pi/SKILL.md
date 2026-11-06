---
name: pi
description: >-
  Run the pi coding agent (pi.dev) with the owner's Claude accounts through the subscription, not an API key — on the Mac via the pi-claude-bridge extension, choosing the account (the main or the secondary one) by CLAUDE_CONFIG_DIR; check which account each folder has; install or repair the bridge; and see how pi reaches its providers on the VPS. Every action is a script in scripts/. Use when the user says "roda o pi", "pi com a conta do Claude", "pi com a conta principal", "usa o pi.dev aqui", "pi via cli", "as contas do pi", "o pi da VPS", "instala o bridge do pi". Not `delegate` (another Claude Code session) nor `bili` (the Hermes agent that launches pi robots on the VPS): this one runs pi itself, here.
metadata:
  version: 0.3.2
---

# pi — o pi.dev com as contas do Claude

O `pi` é o agente de terminal (pi.dev) que roda os robôs da VPS e que também está no Mac. No Mac, ele usa o Claude **pela assinatura**, pela extensão `pi-claude-bridge`. A extensão chama o Claude Code pelo Agent SDK, então o pi usa os logins que o Claude Code já tem, e a conta se escolhe pelo `CLAUDE_CONFIG_DIR`. O detalhe (onde está cada coisa, a VPS) fica no `.wiki/pi.md` do repo da casa.

| Conta | Nome e pasta (`CLAUDE_CONFIG_DIR`), no `casa.env` |
|---|---|
| principal | `$CASA_CONTA_PRINCIPAL_NOME`, em `$CASA_CONTA_PRINCIPAL_DIR` |
| secundária | `$CASA_CONTA_SECUNDARIA_NOME`, em `$CASA_CONTA_SECUNDARIA_DIR` |

`S` abaixo é `scripts/` desta skill. Nenhum script lê stdin, e nenhum imprime token.

## Passos

1. **Pronto e na versão mais nova?** `S/instalar.sh` confere o pi, instala o `pi-claude-bridge@0.9.3` se faltar e lista os modelos `claude-bridge/...`. `S/atualizar.sh [mac|vps|tudo]` põe todo pi na versão mais nova: o do Mac, o do `root` da VPS (pnpm global) e os dos usuários de `$CASA_VPS_USUARIOS_PI`, com as extensões e os catálogos. No fim, ele confere os logins OAuth do `root`. Ele não troca o pi da VPS se houver um rodando. Uma extensão com versão fixa (`@x.y.z`) não sobe sozinha: o script a lista. Antes de trocar a versão do bridge, leia o código do pacote novo (`npm pack`), porque ele roda com as permissões do pi.
2. **Qual conta?** Use a conta da empresa do trabalho em questão: a principal para o trabalho dela, a secundária para o resto. Se não souber, pergunte. `S/contas.sh` mostra o e-mail e a organização de cada pasta, e `S/contas.sh --teste` faz o pi responder "ok" por cada uma.
3. **Rodar:** `S/pi-claude.sh <conta> [args do pi]` (o nome da conta principal ou da secundária).
   - Uma pergunta: `S/pi-claude.sh <conta> -p "<pedido>"`.
   - Outro modelo: `--model claude-bridge/claude-haiku-4-5` (o padrão é `claude-bridge/claude-sonnet-5`, ou `$PI_CLAUDE_MODEL`).
   - Interativo: `S/pi-claude.sh <conta>`, e dentro dele `/model` para trocar o modelo.
   - Passe sempre `--model claude-bridge/...` ou deixe o script pôr. Sem isso, o pi cai no padrão do `settings.json` (`zai/glm-5.3`), e os `~anthropic/...` da lista são da OpenRouter, que cobra por token.
   - **GLM pelo Coding Plan (o outro plano fixo):** `ZAI_API_KEY="$(cat ~/glm_token)" pi -p --no-session --mode json --model zai/glm-5.3 "<pedido>"` (ou `zai/glm-5.3-flash`). A chave entra só no ambiente do processo filho; nunca a imprima nem a ponha num arquivo do repo.
   - **Sem interação, para orquestrar:** `-p --no-session --mode json > <scratch>/run.jsonl`; o fim da execução é o evento `agent_end` (a resposta final em `.messages[-1].content[].text`), e o uso por turno vem em `message_end`/`turn_end` `.message.usage` (`input`, `output`, `cost.total`, que é preço de tabela, não cobrança do plano).
3b. **Comparar modelos na mesma tarefa** (quando o dono quer saber "funciona neste modelo?"): um worktree e um ramo por modelo a partir do `origin/main` (`git worktree add ../<repo>.wt-<tarefa>-<modelo> -b run/<tarefa>-<modelo> origin/main`), o mesmo brief num arquivo fora dos worktrees, e os dois `pi -p` em paralelo num só `terminal(background=true, notify=true)` com `( ... ; echo "<modelo> exit=$? $(date +%s)" >> done ) &` e `wait`. Depois, confira você mesmo os testes de cada ramo, monte a tabela (tempo, testes, o que faltou, custo) e escolha um ramo para o PR, dizendo por quê; registre o resultado de cada modelo, inclusive o não escolhido, para aprender que tarefa cada um faz bem. Só planos fixos entram: Claude pela conta da empresa do trabalho e o GLM do Coding Plan, nunca OpenRouter.
3c. **Delegar uma entrega ao pi** (o executor padrão da casa): o brief num arquivo do scratch (o que fazer, o que não tocar, o "Done" que ele mesmo roda: build, testes, commit pelo caminho, sem push, sem instalar nem abrir app), um worktree novo de `origin/main` depois de conferir que o clone principal está limpo, e `S/pi-claude.sh <conta> -p --no-session --mode json --model <modelo> "Read the file <brief> and implement it fully..."` num `terminal(background=true, notify=true)`.
   - **Uma tarefa, um worktree, criado e removido pelo worktrunk** (`wt`): `wt switch -c <tarefa> --base origin/main --no-cd` para começar, o PR sai desse worktree, e com o PR juntado `wt remove <tarefa>`: ele só apaga o worktree e o ramo quando o conteúdo já está no main (`⊂`), e é essa a garantia de que é seguro apagar; nunca `-D` (ramo não juntado é decisão do dono). `wt list` mostra o que sobrou.
   - **Um pi por worktree.** Para mudar o pedido no meio, mate a execução antiga antes de relançar com o brief novo: duas no mesmo worktree se sobrescrevem.
   - **Acrescentar ao brief com o pi já rodando não chega a ele:** ele leu o arquivo no começo. Um acréscimo pequeno, faça você quando ele voltar (e diga isso ao dono); um grande, mate e relance.
   - **Ao voltar, leia o fim do relato inteiro** (`agent_end`), não só o rabo: o "não feito" e os "comportamentos que você não especificou" ficam no meio e viram correção sua antes do merge (uma etapa de funil que deixa a linha fora de ordem, um embed vazio). Um `exit 0` com `| tail` no meio do relato dele não prova teste verde.
   - **Ao voltar, confira só a lacuna** que o relato dele diz não ter provado (o app na tela, um build que a permissão barrou, o clique de verdade numa janela), corrija, e só então abra o PR como o app.
   - **Vários pis no mesmo arquivo ao mesmo tempo** (cada um no seu worktree): diga em cada brief o que o outro está mudando e o que este pode tocar ("só a barra e o overlay, não o `drawGraph`"), e junte na ordem em que voltam. O que volta depois traz o `origin/main`; um conflito de código se resolve **pelo sentido**, juntando as duas regras numa só (nunca escolhendo um lado), e se os dois mexeram no mesmo modelo de dados (duas formas de `D.modules`), aborte o rebase e dê ao pi um brief de "aterrissar" o commit sobre o main novo, com o modelo único descrito. Depois de juntar, rode o console de teste e confira na tela antes do merge.
   - **PRs paralelos no biliboss/skills colidem na versão do plugin e no CHANGELOG da raiz:** ao juntar o segundo, traga o `origin/main`, dê a ele a próxima versão e reordene o CHANGELOG da mais nova para a mais antiga (um script que ordena as seções `## [x.y.z]`), nunca empilhando duas entradas com o mesmo número.
   - **Swift no Mac:** se o `swift build` acusar SDK trocado, `export SDKROOT=$(xcrun --sdk macosx --show-sdk-path)` no brief e nos scripts de build.
4. **As nossas skills no pi:** `S/ligar-skills.sh` liga em `~/.pi/agent/skills/` cada skill deste plugin (`biliboss/skills`), lida do `plugin.json`, e tira do caminho a que saiu do plugin. Rode depois de criar ou tirar uma skill; no pi aberto, mande `/reload`.
5. **A VPS:** `S/vps.sh` mostra, para cada `~/.pi/agent` da VPS, os provedores logados (só o tipo), o padrão e se o `anthropic` está pronto. Lá o `root` usa o login do próprio pi (`anthropic` por OAuth), não o bridge.

## O que pega

- **O login OAuth da pasta não vai para o envless nem é copiado entre máquinas** (nem o `~/.pi/agent/auth.json`, nem a pasta do Claude Code): o token se renova a cada uso, e a cópia envelhece e pode derrubar o login da outra máquina. O token do `claude setup-token` é fixo por 1 ano e vai para o envless, como as chaves `zai` e `kimi`.
- **Login é do dono:** o OAuth acontece no navegador, e o agente não o conclui sozinho. Peça `! CLAUDE_CONFIG_DIR=<pasta> claude auth login` (uma conta no Claude Code) ou `! pi` seguido de `/login` (o login do próprio pi, como na VPS).
- **`pi --list-models` só mostra os modelos `zai` com `ZAI_API_KEY` no ambiente:** sem ela, o GLM parece não existir. Confira com `ZAI_API_KEY="$(cat ~/glm_token)" pi --list-models | grep glm`.
- **O catálogo do `claude-bridge` vem do pi e pode estar atrás** dos modelos novos. Confira com `pi --list-models claude-bridge` antes de pedir um modelo, e atualize com `S/atualizar.sh mac`.
- **`pi auth check --no-refresh` diz "ready" mesmo com o token de renovação vencido:** ele só vê que a credencial existe. Para saber se o login vale, rode sem `--no-refresh`. "invalid" pede um `/login` novo do dono.
- **O bridge para o turno se outra extensão mexer no prompt de sistema do pi,** porque a Anthropic poderia cobrar como uso extra. `CLAUDE_BRIDGE_DEBUG=1` grava o prompt em `~/.pi/agent/claude-bridge.log`.
- **O `/goal` é o do `@narumitw/pi-goal`; não instale o `pi-goal-x` no pi global:** os dois registram `/goal`, e o auditor do `pi-goal-x`, rodando pelo `claude-bridge`, não devolve o marcador de aprovação e deixa o goal `blocked` com o trabalho pronto.
- **Para testar uma extensão sem trocar o pi de todos:** instale-a numa pasta à parte (`npm install --prefix <pasta> <pacote>`) e rode `pi -ne -e <bridge> -e <extensão>`, com os caminhos do campo `pi.extensions` de cada `package.json` (o bridge: `~/.pi/agent/npm/node_modules/pi-claude-bridge/src/index.ts`). O `-ne` desliga as extensões globais, então passe também as que o teste precisa (ex.: `~/.pi/agent/extensions/herdr-agent-state.ts`, para o herdr ver o estado).
- **Um `pi -p` com o bridge leva de 10 a 60 s** (ele sobe um Claude Code por chamada). Num laço, rode em segundo plano.
- **Troca de conta com tokens (`pi-claude-accounts`):** o `setup-token` autoriza na conta do navegador padrão, não na do `CLAUDE_CONFIG_DIR`. A receita (gerar na conta certa, guardar no envless sem ver, conferir, levar ao pi, prazos) está em [references/contas-tokens.md](references/contas-tokens.md).
