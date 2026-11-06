---
name: linear
description: >-
  Work the owner's Linear (workspace `$CASA_LINEAR_WORKSPACE`, team `$CASA_LINEAR_TIME_CHAVE`) the way he wants it: read a project before touching it, write the project's description and content, create result cards with an owner and a way to check, keep milestones honest, and post project updates that read well (O Alquimista style) with images and links. The main path is the official Linear MCP through mcpc (@linear, the Bili app's voice), wrapped by scripts/linear.sh; the scripts cover what the MCP does not (a project snapshot, image upload, the owner's own inbox). Use when the user says "atualiza o projeto no Linear", "cria os cartões", "posta um update", "o update não apareceu", "revisa o marco", "põe no Linear", "update the Linear project". Not `to-tickets` (turns a plan into tickets anywhere) nor `bili` (asks the Hermes agent to do work): this one edits Linear itself.
metadata:
  version: 0.3.2
---

# linear — o Linear do dono, do jeito dele

O Linear é o quadro do foco do dono: ele bate o olho e sabe o que está andando, o que espera alguém e o que acabou. Tudo o que um agente escreve lá sai com uma voz só, a do **app Bili**. As regras de fundo (os níveis, o tamanho dos cartões, o que é produção) estão no doc do time **"AGENTS.md · como os agentes usam este Linear"**, e o técnico do biliboss está no `.wiki/linear.md` do repo da casa (`$CASA_REPO_PRINCIPAL`).

`S` abaixo é `scripts/` desta skill. Os ids fixos (time, dono, app, estados, status de projeto) vêm do `casa.env`, lidos pelo `S/ids.sh` (`$CASA_LINEAR_*`). Nenhum script imprime token.

## As vozes

| Para | Use |
|---|---|
| Ler e escrever como agente (o padrão) | `S/linear.sh <ferramenta> arg:=json …`, que chama o `mcpc @linear` (o MCP oficial do Linear, com o OAuth do app Bili). Na primeira vez, veja os parâmetros da ferramenta com `S/linear.sh --ver <ferramenta>` |
| O que o MCP não faz (marco com progresso, upload, introspecção) ou quando o login do `@linear` venceu | `S/lin.sh '<query GraphQL>' [vars.json]`: a mesma voz do app, pelo `linear-gql` da VPS |
| Ler o que é do dono (a inbox, as preferências de notificação) | `S/dono.sh '<query>'`, com a chave pessoal do Keychain. Escrever em nome dele, só com o OK dele |

Se o `@linear` não responder, o `S/linear.sh` tenta `mcpc @linear restart`. Se não voltar, siga pelo `S/lin.sh` e avise o dono. **Nunca use `mcpc login` no `@linear`:** o navegador aprova na hora a conta do dono, e o token sai em nome dele. O app entra por header Bearer, pelo passo 8 do roteiro do app no `.wiki/linear.md` do repo da casa.

**Marcar o Bili** (para ele agir num cartão): no comentário, a menção vai como o link do perfil do app, `[@bili]($CASA_BILI_PERFIL_URL)`, e o comentário sai de uma pessoa, por `S/dono.sh` (`commentCreate`) ou pelo clique do dono. O que o próprio app escreve não abre sessão, e o duplo-server ignora, para o Bili não responder a si mesmo. Por isso um pedido ao Bili da VPS sai pelo `linear-bili.sh pedir <cartão> <arquivo.md>` da skill `bili`, que comenta pela conta do dono, e nunca pelo `S/lin.sh` nem pelo `S/linear.sh`. Ao delegar a um subagente um recado ao Bili, escreva isso no briefing. Num cartão, a menção abre uma sessão de agente, e o pedido segue pelo webhook e pelo duplo-server até o NATS (`entrada.linear.agente` e `tarefa.criada`) e ao Bili. A confirmação aparece no painel de agente do cartão: uma atividade "thought" em cerca de 10 s e, depois, a resposta.

## Onde a conversa mora

O Linear é o lugar de toda a conversa. Escolha o nível antes de escrever:

| Nível | Onde se conversa |
|---|---|
| Cartão | os comentários; a menção ao Bili abre a sessão de agente (é o caminho que ele ouve) |
| Milestone | **não tem comentário**: crie um **cartão de conversa** no marco (os pedidos ao Bili e as respostas) e um **Doc do marco** com o resultado (a decisão no topo, uma seção por protótipo com o print e o link do clicável, os prós e contras) |
| Projeto | os **project updates** (o estado da semana, com fio) e os comentários do projeto |
| Doc | os comentários no texto, entre pessoas |

- Pedido ao Bili fora de um cartão (comentário de projeto ou de Doc) só chega quando o app tiver "Inbox notifications" e o duplo-server tratar o tipo (`projectCommentMention`, `documentCommentMention`); o estado está no `.wiki/linear.md` do repo da casa ("Onde a conversa mora"). Na dúvida, peça no cartão de conversa.

## Passos

1. **Ler as regras e o projeto antes de escrever.** Leia o doc do time pelo MCP (`get_document`, id em `$CASA_LINEAR_DOC_AGENTS_ID`), uma vez por sessão. Depois, `S/projeto.sh <id ou url>` mostra o status, os membros, cada marco com o progresso e os cartões, os cartões sem marco e o último update. Procure um cartão que já exista antes de criar outro: um espelho de issue do GitHub pode estar fora do projeto. Se estiver, ponha-o no projeto em vez de duplicar.
   - **Leia também os docs do projeto** (`project { documents(first:30){nodes{id title updatedAt}} }`, depois `document(id){content}`) antes de produzir qualquer coisa nele. Os docs guardam as premissas mais novas: quando um doc contradiz o conteúdo do projeto ou os cartões antigos, vale o doc mais recente. Cartão antigo é material de pesquisa, não o padrão a seguir.
2. **O projeto.**
   - A descrição é uma frase do que o produto faz e para quem.
   - O conteúdo tem cinco partes: o que é, onde está (repo, wiki, cartão do GitHub), as pessoas, as versões, o estado com a data e o que fica fora do escopo.
   - **Um projeto é um projeto:** nunca cite tensão nem `tension.md`.
   - O status diz quem tem a bola: 🤖 Clone construindo, ✋ Espera uma pessoa, 📈 No ar, medindo ou ✅ Resultado visto.
3. **Os cartões.**
   - Um cartão é um **resultado**, não uma tarefa. O título diz o que passa a ser verdade ("O servidor de demonstração fica no ar").
   - O corpo tem quem faz (👤 pessoa ou 🤖 agente), **Objetivo:** numa frase, **Como conferir:** com um teste, uma URL ou um número, e os links (PR, spec).
   - O responsável é sempre o dono.
   - Trabalho de agente é do app Bili (`$CASA_LINEAR_APP_BILI_ID`), numa sessão só por cartão: delegar já abre a sessão dele, e uma menção depois abre outra. Para pedir com contexto, crie sem delegado e marque-o uma vez (skill `bili`); cartão já delegado não leva menção nova.
   - O passo que só uma pessoa faz (merge, conta, segredo, conversa com o cliente) fica sem delegado.
   - **Dois níveis.** O **pai** é o que tem valor para o dono, em linguagem de diretoria: o título diz o resultado para o negócio numa linha, sem jargão, e a descrição tem 3 linhas (o que muda para quem usa, por que importa para o negócio, como saberemos que deu certo). Quem lê só os títulos dos pais, de cima para baixo, entende a versão. O **subcartão** é o trabalho que um agente faz sozinho, em paralelo, em 10 a 30 min, e que entrega algo que se vê ou se confere, com um Como conferir que alguém de fora entende. Passo que depende de outro vira um subcartão só; passo que não é trabalho de agente (uma conferência, esperar dados, a chave do dono) vira item de checklist. Sem esse critério, a divisão vira dezenas de cartões soltos que ninguém lê.
   - **Cada subcartão vale por si** (o seu Como conferir) e delegá-lo ao Bili abre uma sessão por cartão: crie só os que valem a sessão. Checklist é só para o que não é trabalho de agente; passando de uns 5 por pai, junte.
   - **Toda decisão de criar, dividir ou juntar cartões publica `mesa.agent.decision.made`** (`issue`, `choice`, `why` até 120 caracteres, `turn_id`, `trace_id`) e vira o comentário "Decidi X porque Y" no pai. Cartão com sessão de agente ativa não muda de estado: só título, pai, junção e comentário.
   - **Ordem dos pais = a jornada do usuário** (`sortOrder`); o control plane e o quadro seguem essa ordem.
   - Antes de criar um pai ou subcartão, procure se já existe (`searchIssues(term:"…")`, em qualquer projeto e marco) e reaproveite.
   - **Cancelar é reversível, apagar não.** Cartão velho, repetido ou sem sentido: cancele e comente "Decidi cancelar porque…" (repetido vai para Duplicate, com a relação `duplicate` criada antes). Apagar continua sendo do dono.
4. **Os marcos contam a verdade.**
   - **Marco é versão, não frente.** Todo projeto tem um marco ativo (a versão em curso, ex.: "<Projeto> V1.0") e o **Backlog** por último na ordem (`sortOrder` maior): o que não tem versão vai para ele. Uma versão aberta por vez; a próxima nasce quando a ativa fecha, puxando do Backlog. A frente (Busca, Login…) é **label** no cartão, para filtrar sem marco.
   - **Reorganizar um projeto por versão:** guarde antes uma foto (cartão, estado, marco, labels) num arquivo, para desfazer; classifique cada cartão aberto na versão ou no Backlog com uma linha de porquê, numa tabela num comentário do cartão de conversa; crie só as labels que faltam (compare sem caixa); se o trabalho está no ar ou outro agente mexe nesses cartões, avise no cartão de conversa antes de mover; mova e ponha a label; apague o marco antigo só vazio; renomeie um marco em vez de criar outro.
   - **As fases são só Todo → Doing → Done.** "Backlog" é o marco, não o status: o status Backlog fica no time sem uso (o Linear não deixa arquivar o último do tipo), e o padrão de cartão novo é Todo (`teamUpdate(defaultIssueStateId)`). Não existe In Review: PR aberto é trabalho do agente em Doing. Doing é só o que um agente faz agora; o resto volta para Todo. Planejar (título de resultado, Como conferir, marco e label certos) é a condição para estar no marco da versão ativa. Leia o estado dos PRs (`gh pr view`) antes de mover.
   - **Reescrever cartões em lote:** primeiro um rascunho num arquivo, com UMA tabela "marco | cartão | título antigo → novo | estado antigo → novo | por quê | juntar com" e a descrição nova de cada um. Depois aplique e registre (o sistema é autônomo); espere o OK do dono só se o pedido disser "mostre antes". Citação do relato de uma pessoa nunca é inventada: sem as palavras dela, escreva "paráfrase".
   - **Goal "zerar o Doing":** liste o Doing do marco ativo (pais e subcartões, `state:{type:{eq:"started"}}`) e tire dele o que ninguém faz agora (um pai que só começa quando os outros estiverem no ar volta para Todo, com o "Decidi" no cartão). O cartão de conversa fica fora. Depois mande um pedido por cartão ao agente que faz, com o contexto inteiro: o goal, o que é Done ali, a permissão de merge depois da revisão por agente se o dono a deu, o WIP (sem subcartão novo; use checklist) e os quatro casos que esperam o dono. Até o Doing zerar, nada novo entra em Doing.
   - **Acompanhar o goal sem fazer o código:** um subagente local por cartão lê o estado, as atividades da sessão de agente, os comentários e o PR; só comenta (pelo `linear-bili.sh pedir`) se o agente está parado há mais de 15 min, com o próximo passo concreto, e devolve uma linha para o dono só nos quatro casos, com o comando exato. Antes de cobrar, confira se o bloqueio já saiu (uma chave posta no cofre depois do pedido): avise o agente com os nomes, nunca os valores.
   - **Trava técnica não é caso do dono.** Um PR em `REVIEW_REQUIRED`/`BLOCKED` com revisão de agente feita, uma permissão de app ou uma configuração que barra o trabalho não entram nos quatro casos: diga a trava pelo nome (`gh api repos/<o>/<r>/rulesets` mostra qual ruleset exige code owner) e proponha tirá-la ou contorná-la. Nunca escreva "espera o dono: aprovar o PR": lido como decisão dele, o cartão para em vários relatos seguidos sem ninguém agir.
   - **Feche o cartão do goal quando o Done dele já está cumprido** (ex.: o Done era "PR mergeado" e o PR entrou): mova para Done você mesmo, com o "Decidi" e o link, em vez de esperar o agente remoto voltar ao cartão. Releia o estado real dos PRs (`gh pr view --json state,mergedAt`) antes de relatar o "N de M".
   - **O marco ativo pode ser um tema, quando o dono diz qual é** (ex.: "aplicar o design system"): dê a ele o título de diretoria, mova todo o resto ao Backlog e ordene os pais pela jornada (base visual → componentes → telas na ordem em que o usuário passa). Subcartão só nasce depois de ler o material-fonte (o design system, o Doc): sem ele, a divisão é palpite.
   - **Material-fonte que ainda não dá para ler** (falta o login do dono, o arquivo está noutro lugar) não trava o marco: ligue ao projeto o que já existe (`entityExternalLinkCreate` com `projectId`: a pasta, a ata da reunião que decidiu o marco), cite a ata na descrição do marco como fonte da decisão e ponha no checklist do primeiro pai "o arquivo: aguarda o login", com o comando exato do login no relato.
   - **Subcartão fica no marco do pai.** Um subcartão num marco diferente do pai (ex.: o pai no V1.0 e os filhos no Backlog) some da tela da versão; confira e corrija ao reorganizar.
   - O que já foi feito ganha um cartão em Done no marco, com o link do PR e das provas. Sem ele, o marco mede 0% de algo quase pronto.
   - Um update nunca diz "pronto" enquanto o marco tem cartão aberto: diga "construído e aprovado; falta pôr no ar".
5. **O update do projeto.**
   - **O que importa vem primeiro:** o estado numa frase de título, depois o que falta, com o dono e o cartão de cada passo, depois o porquê.
   - **Escreva gostoso de ler, na régua do Alquimista** (`moc-copywriting` e `escrever-bem` no wiki do repo da casa): frase curta, palavra de todo dia, tom de conversa, uma imagem simples que volta como refrão e um fecho que resume.
   - **Tire o jargão:** nada de hash de commit nem caminho de pasta, e "juntar o PR" em vez de "mergear".
   - **Imagem:** `S/upload.sh <arquivo>` sobe o arquivo e devolve a URL do Linear; no texto, use `![descrição](URL)`. A imagem de um repo privado do GitHub não abre no Linear.
   - **Um link para um Claude Artifact é privado até o dono compartilhar:** avise.
   - A saúde é `onTrack`, `atRisk` ou `offTrack`, com honestidade: prazo perto e nada andando é `atRisk`.
   - Para conferir a escrita, peça a outro modelo uma revisão contra a régua (a skill `pi` faz isso pela conta do Claude) e aplique o que fizer sentido, sem trocar o significado.
6. **Espelho num GitHub Project** (quando o time de fora acompanha pelo GitHub): o Linear é a fonte e o espelho é de mão única. Receita em `references/github-project-mirror.md`.
7. **Notificar.**
   - Editar um update não avisa ninguém. Para avisar, poste um update novo.
   - **Para o dono receber, marque-o no texto do update** (`[@Nome](<url do perfil dele>)`); sem a menção, o update não chega à inbox.
   - **O update traz "O que decidi e por quê", nunca "o que espera a decisão dele".** O sistema é autônomo: diante de uma decisão, o agente escolhe a própria recomendação, age e comenta no cartão "Decidi: X, porque Y. Se quiser outro caminho, é só dizer." Só quatro coisas esperam o dono: dinheiro, login ou conta, publicar para fora e apagar. Essas vão numa linha "Espera o dono", cada uma com o tipo.
   - Se o dono diz que um update não chegou à inbox dele, leia as notificações e as preferências com `S/dono.sh` antes de supor a causa.

## O que pega

- **O limite de complexidade da API é 10000:** ponha `first:N` em toda lista aninhada (`members`, `projectMilestones`, `issues`), ou a query volta "Query too complex".
- **Várias mudanças vão numa chamada só,** com aliases (`a: issueUpdate(...) b: issueUpdate(...)`) e os textos em variáveis. Dentro da query, um enum vai sem aspas (`health:onTrack`), senão a API recusa.
- **`project.documents` pode voltar vazio com os docs existindo:** um agente de fora (o ChatGPT com o conector do Linear) cria os Docs e os lista só no corpo de um cartão. Se a lista vem vazia, procure links `/document/` na descrição dos cartões do marco antes de concluir que o projeto não tem docs.
- **`Project` não tem `links`:** os links de um projeto estão em `externalLinks`.
- **O `progress` de um marco já vem em porcentagem:** não multiplique por 100.
- **Ao ler `agentSessions → activities`, pule as marcadas `ephemeral`:** o Linear manda uma cópia provisória de cada ação antes da definitiva, e quem republica as duas mostra cada passo em dobro.
- **Num rascunho de lote, confira as decisões já registradas nos cartões contra as mais novas:** dois comentários "Decidi" podem se contradizer (um nome de marco, por exemplo); siga o mais recente e diga isso na tabela.
- **O Linear reescreve o `sortOrder` de cartões criados em sequência** (valores como -250317 no lugar do -700 pedido). Depois de criar os pais, grave a ordem de novo numa chamada só, com valores espaçados (1000, 2000, 3000…), e confira lendo de volta.
- **O `lin.sh` é o caminho normal de escrita como app**, não um acesso à conta de outro agente: um veto a SSH/sudo no usuário do Bili da VPS (ler o banco dele) não proíbe o `lin.sh`. Diga isso no briefing de quem escreve no Linear, senão o subagente para sem aplicar nada.
- **Uma chamada pelo `lin.sh` leva de 5 a 60 s** (ela passa pela VPS). Num lote de cartões, rode em segundo plano e confira no fim com `S/projeto.sh` se nada saiu repetido.
- **Projeto novo atrai outro agente:** o Bili da VPS (ou outra sessão) pode criar, em paralelo, o mesmo cartão de resultado ao ver o projeto nascer. Logo depois de criar, rode `S/projeto.sh` e procure títulos parecidos. Se houver duplicata, leve o que o outro tem a mais (checklist, links) para o cartão que seguiu o pedido e cancele o outro como Duplicate, pela regra do passo 3 (cancelar é reversível; só apagar espera o dono). Se o outro cartão é de um agente que ainda trabalha nele, peça a ele no cartão de conversa em vez de cancelar por cima.
- **Antes de delegar a criação de um projeto, avise no plano quem cria os cartões:** briefing com "só você cria cartões neste projeto" não impede o Bili da VPS. Se o pedido nasceu da conversa com o dono, diga no relato que pode surgir cartão paralelo.
