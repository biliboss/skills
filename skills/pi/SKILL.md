---
name: pi
description: >-
  Run the pi coding agent (pi.dev) with the owner's Claude accounts through the subscription, not an API key — on the Mac via the pi-claude-bridge extension, choosing the account (the main or the secondary one) by CLAUDE_CONFIG_DIR; check which account each folder has; install or repair the bridge; and see how pi reaches its providers on the VPS. Every action is a script in scripts/. Use when the user says "roda o pi", "pi com a conta do Claude", "pi com a conta principal", "usa o pi.dev aqui", "pi via cli", "as contas do pi", "o pi da VPS", "instala o bridge do pi". Not `delegate` (another Claude Code session) nor `bili` (the Hermes agent that launches pi robots on the VPS): this one runs pi itself, here.
metadata:
  version: 0.3.0
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
   - **A troca sozinha (extensão `pi-claude-accounts`):** o pi gasta a principal primeiro e só passa à reserva quando ela chega a 95% do limite de 5 h; volta à principal no primeiro prompt depois que ela renova. Roda o fork do biliboss (`~/src/pi-claude-accounts`, ramo `prioridade`), instalado de uma worktree fixa no commit revisado (`~/.pi/agent/forks/pi-claude-accounts`); o original sorteia a conta e não volta. A ordem fica em `~/.pi/agent/claude-accounts-priority.json`, que as instâncias antigas não apagam.
   - **Os tokens moram no envless** (cofre `~/.cofre-claude`, env `claude`, chaves `CLAUDE_TOKEN_<NOME>`). `CASA_CLAUDE_PRIORIDADE="<principal> <reserva>" S/contas-tokens.sh --sem-login` leva-os ao `claude-accounts.json` (0600) sem o valor passar por tela ou log; num pi aberto, `/reload` e `/claude-accounts refresh`.
3. **Rodar:** `S/pi-claude.sh <conta> [args do pi]` (o nome da conta principal ou da secundária).
   - Uma pergunta: `S/pi-claude.sh <conta> -p "<pedido>"`.
   - Outro modelo: `--model claude-bridge/claude-haiku-4-5` (o padrão é `claude-bridge/claude-sonnet-5`, ou `$PI_CLAUDE_MODEL`).
   - Interativo: `S/pi-claude.sh <conta>`, e dentro dele `/model` para trocar o modelo.
   - Passe sempre `--model claude-bridge/...` ou deixe o script pôr. Sem isso, o pi cai no padrão do `settings.json` (`zai/glm-5.3`), e os `~anthropic/...` da lista são da OpenRouter, que cobra por token.
4. **As nossas skills no pi:** `S/ligar-skills.sh` liga em `~/.pi/agent/skills/` cada skill deste plugin (`biliboss/skills`), lida do `plugin.json`, e tira do caminho a que saiu do plugin. Rode depois de criar ou tirar uma skill; no pi aberto, mande `/reload`.
5. **A VPS:** `S/vps.sh` mostra, para cada `~/.pi/agent` da VPS, os provedores logados (só o tipo), o padrão e se o `anthropic` está pronto. Lá o `root` usa o login do próprio pi (`anthropic` por OAuth), não o bridge.

## O que pega

- **O `claude setup-token` usa a sessão do navegador padrão,** e no Mac o padrão é o Safari: com o claude.ai logado lá na outra conta, ele autoriza sozinho e o token sai da conta errada. Rode com `BROWSER=/usr/bin/true` (não abre nada), abra o link no perfil certo do Chrome (`open -a "Google Chrome" --args --profile-directory=<perfil> "<url>"`, sempre na mesma aba), confira o "Logged in as" antes do Authorize e cole o código (`código#state`) no pane. Confira depois: o uso e o reset de 5 h de cada token têm de ser diferentes.
- **O token do `setup-token` vale 1 ano e não se renova; o login da pasta (`claude auth login`) renova o acesso a cada uso, mas o token de renovação tem prazo fixo (semanas)** e o Claude Code avisa 3 dias antes. Anote a data de cada token e deixe um cartão no Linear antes de vencer. Gerar outro não revoga o antigo: revogue em claude.ai › Settings › Claude Code.
- **Uma conta Max com pouco uso não manda a janela de 5 h** (só a de 7 dias): o `/claude-accounts` mostra `n/a`, e a extensão a trata como vazia.
- **O login OAuth do Claude não vai para o envless nem é copiado entre máquinas** (nem o `~/.pi/agent/auth.json`, nem a pasta do Claude Code): o token se renova a cada uso, e a cópia envelhece e pode derrubar o login da outra máquina. O token do `setup-token`, que é fixo por 1 ano, vai para o envless (o cofre `~/.cofre-claude`), como as chaves `zai` e `kimi`.
- **Login é do dono:** o OAuth acontece no navegador, e o agente não o conclui sozinho. Peça `! CLAUDE_CONFIG_DIR=<pasta> claude auth login` (uma conta no Claude Code) ou `! pi` seguido de `/login` (o login do próprio pi, como na VPS).
- **O catálogo do `claude-bridge` vem do pi e pode estar atrás** dos modelos novos. Confira com `pi --list-models claude-bridge` antes de pedir um modelo, e atualize com `S/atualizar.sh mac`.
- **`pi auth check --no-refresh` diz "ready" mesmo com o token de renovação vencido:** ele só vê que a credencial existe. Para saber se o login vale, rode sem `--no-refresh`. "invalid" pede um `/login` novo do dono.
- **O bridge para o turno se outra extensão mexer no prompt de sistema do pi,** porque a Anthropic poderia cobrar como uso extra. `CLAUDE_BRIDGE_DEBUG=1` grava o prompt em `~/.pi/agent/claude-bridge.log`.
- **O `/goal` é o do `@narumitw/pi-goal`; não instale o `pi-goal-x` no pi global:** os dois registram `/goal`, e o auditor do `pi-goal-x`, rodando pelo `claude-bridge`, não devolve o marcador de aprovação e deixa o goal `blocked` com o trabalho pronto.
- **Para testar uma extensão sem trocar o pi de todos:** instale-a numa pasta à parte (`npm install --prefix <pasta> <pacote>`) e rode `pi -ne -e <bridge> -e <extensão>`, com os caminhos do campo `pi.extensions` de cada `package.json` (o bridge: `~/.pi/agent/npm/node_modules/pi-claude-bridge/src/index.ts`). O `-ne` desliga as extensões globais, então passe também as que o teste precisa (ex.: `~/.pi/agent/extensions/herdr-agent-state.ts`, para o herdr ver o estado).
- **Um `pi -p` com o bridge leva de 10 a 60 s** (ele sobe um Claude Code por chamada). Num laço, rode em segundo plano.
