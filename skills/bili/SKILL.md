---
name: bili
description: Hand a request to Bili, the owner's Hermes agent, by one of three routes chosen by configuration (CASA_BILI_ROTA, default local) through a single script, bili.sh pedir|esperar|ler|rota. local = an event on the Mac's NATS for the local Bili; remoto = an event on the VPS NATS for the VPS Bili; linear = a mention on the Linear card where the subject lives (project or card work). The Mac request is grilled first (method from the skill `grilling`; mode CASA_BILI_GRILL=ask|interview|plain), one binary question at a time. Never the Hermes API, SSH or duplo MCP. Also waits for and reads the reply, and shows or switches the route. Use when the user says "troca a rota do bili", "pede pro bili", "manda pro bili", "roteia pro bili", "pergunta pro bili", "marca o bili", "o que o bili respondeu", "em que pé o bili está". Not `linear` (that edits Linear itself) nor `herdr-agentes` (other agent sessions in herdr) nor `delegate-and-review` (a subagent that opens a PR); this one asks the agent that keeps the memory.
metadata:
  version: 0.8.0
---

# bili — mandar um pedido ao Bili

## A rota: local, remoto ou Linear

Uma porta só: `scripts/bili.sh` (`B=<pasta desta skill>/scripts/bili.sh`). A rota vem do `casa.env` (`CASA_BILI_ROTA`, padrão `local`).

| Rota | O que faz | Use quando |
|---|---|---|
| `local` | publica um evento no NATS do Mac; o Bili local pega e responde por evento | pedido de dia a dia do Mac (padrão) |
| `remoto` | publica um evento no NATS da VPS (pela tailnet); o Bili da VPS pega | o trabalho é da VPS (clones, Ansible, o que roda lá) |
| `linear` | uma menção ao Bili num cartão do Linear (seções 1 a 5) | **trabalho de projeto ou de cartão**: a conversa e o ciclo ficam visíveis no cartão |

```sh
sh $B rota                    # mostra a rota de agora e de onde veio
sh $B rota remoto             # troca: grava CASA_BILI_ROTA=remoto no casa.env
BILI_ROTA=linear sh $B pedir <TIME>-231 pedido.md    # só esta chamada, sem gravar
sh $B pedir pedido.md         # local/remoto: imprime "<trace_id> <desde>"
sh $B esperar <trace_id> 300  # a resposta (evento answered); 124 sem resposta
sh $B ler 5                   # as últimas 5 respostas
```

- **Quando o dono pedir para trocar a rota** ("manda direto pra VPS", "volta pro local"), rode `rota <nome>` e confirme com `rota`.
- **Pedido sobre um projeto ou cartão do Linear** (ex.: Via Corretor) vai pela rota `linear`, mesmo com a rota padrão em `local`: use `BILI_ROTA=linear` na chamada.
- **No linear** os argumentos são os do `linear-bili.sh` (cartão primeiro); nas outras, o arquivo do pedido e o `trace_id`.
- **O evento** segue a gramática do `libs/local-events` do repo da casa: `mesa.agent.request.received` (com `trace_id`, `sender`, `text`) e, na volta, `mesa.agent.request.answered`. O pedido com cara de segredo é recusado.
- **Teste nunca no stream real:** `CASA_BILI_NATS_RAIZ=test` troca a raiz do subject (`test.agent.request.received`).
- **Valores da casa** (`CASA_BILI_NATS_LOCAL_URL`, `CASA_BILI_NATS_REMOTO_URL`, usuário e arquivo da senha, stream) estão no `casa.env.example`. A senha vem de um arquivo e nunca é impressa.
- **O lado de quem recebe** é de cada máquina: no Mac, um trigger do sistema de triggers da mesa; na VPS, uma rota do plugin hermes-jetstream do Bili. Sem ele aplicado, o pedido publicado fica sem resposta (o `esperar` sai com 124).

## 0. No Mac: grill primeiro, depois a rota

Todo pedido do dono feito no Mac vai ao **Bili local** (o Hermes local, no pane `$CASA_BILI_LOCAL_PANE`). É ele quem faz, delega aos subagentes dele ou pede ao Bili da VPS pelo Linear (as seções 1 a 5, que ele mesmo usa). Uma sessão do Mac chama o Bili da VPS direto só quando a rota configurada for `remoto`, ou `linear` para trabalho de projeto.

1. **Grill antes de mandar, sempre.** O método é o da skill `grilling` (grill-me): **carregue-a e siga-a; este texto não a copia**. Sem ela instalada, faça no modo `plain` com as mesmas regras abaixo. O modo vem do `casa.env`, `CASA_BILI_GRILL` (padrão `ask`):

   | Modo | Como pergunta |
   |---|---|
   | `ask` | a ferramenta AskUserQuestion |
   | `interview` | a skill `interview` (o formulário) |
   | `plain` | texto no chat, esperando a resposta |

   Regras, iguais nos três modos:
   - **Antes de perguntar, escreva para si** (nota curta, sem mostrar) quais decisões faltam e em que ordem; só é pergunta o que é do dono (resultado, escopo, quem faz, limite) e que não dá para achar no repo ou no contexto.
   - **Uma pergunta por vez, binária:** duas opções concretas, a recomendada primeiro ("(Recommended)") com o porquê em uma linha, escrita para quem não viu a conversa: o que se decide e o que muda em cada resposta.
   - **Cada resposta escolhe o próximo ramo**; uma resposta confusa pede a mesma pergunta reescrita, nunca uma rodada maior.
   - **Pare quando o Bili puder fazer sem perguntar de novo.**
   - **Pedido já claro: zero perguntas**, e diga isso ("pedido claro, sem grill") antes de mandar.
2. **Escreva o pedido num arquivo** (o scratchpad, ou `~/.local/state/<tema>.md` quando for longo): o objetivo verificável, as decisões do grill com as respostas do dono (ou "sem grill: pedido claro"), o contexto (repo, caminho, commit, cartão), o que não fazer e como responder (em até 5 linhas).
3. **Mande pela rota:** `sh $B pedir <arquivo>` (guarde o `trace_id`), e `sh $B esperar <trace_id>` em segundo plano. Na rota `local`, o evento vira um turno do Bili local, e ele responde com um evento. Para corrigir o rumo de um turno em curso, e só para isso, use o `manda $CASA_BILI_LOCAL_PANE` do `mux.sh` (skill `prime-agent`); a correção urgente, que não pode esperar o turno, vai como steer pelo `manda`.
4. **Junte o que chega junto:** vários pedidos numa mensagem numerada, nunca uma rajada de mensagens soltas.
5. **Arme o monitor do NATS** (se ainda não estiver de pé), pela ferramenta Monitor do Claude Code, com o tempo máximo:
   `uv run -q --script <pasta desta skill>/scripts/watch.py asks errors panes`
   Ele imprime uma linha por evento do NATS local que pede atenção humana, e cada linha vira um aviso na sessão: uma pergunta esperando o dono (`asks`), um erro de verdade (`errors`), um agente que parou ou travou (`panes`). Outros nomes: `cycle` (cada pedido respondido, com o lead time), `llm`, `routes`; `--list` mostra todos. O monitor expira (30 min no Claude Code): rearme quando o aviso de expiração chegar. Num terminal comum, o mesmo comando roda em primeiro plano.
   - **Um aviso é um fato, não uma resposta do dono:** passe ao dono só o que muda o que ele faria (uma pergunta para ele, um agente travado); o resto, ignore.
   - **Os assuntos vigiados vêm de um arquivo** (`$CASA_BILI_WATCH_SUBJECTS_FILE`, JSON `{"asks": ["assunto.*"], ...}`; o nome que não está no arquivo mantém o assunto embutido de hoje). O `watch.py` é autocontido (não importa a lib da casa, a skill é pública): o arquivo só muda onde ouvir, o que cada nome imprime é do formatador.
   - **O próprio pane do dono não gera aviso** (`$CASA_DONO_PANE`, ou uma lista em `WATCH_IGNORE_PANES`); um aviso falso que se repete se corrige no `watch.py`, não ignorando.
   - **Teste de evento nunca no stream real** (um NATS de teste ou um subject `test.>`): o monitor e as views leem o stream real.
6. **Diga ao dono** em poucas linhas o que foi decidido e o que foi ao Bili. A volta se acompanha pelo pane do Bili local e pelos avisos do monitor, nunca esperando em primeiro plano.

## Bili da VPS, pelo Linear

O Bili é o agente de vida longa do dono: um Hermes na VPS (host `$CASA_VPS_HOST`, usuário `$CASA_VPS_USUARIO_BILI`), com memória própria e robôs do pi.dev que ele solta por tarefa. O Claude Code do Mac é só uma porta: quem executa e guarda é o Bili. **O Linear é o único canal**: um pedido é uma menção a ele num cartão, a menção abre a sessão de agente dele, e o pedido segue pelo duplo-server e pelo NATS até ele. A resposta volta no mesmo cartão. Nunca fale com ele direto (nada da API do Hermes, de SSH no usuário do Bili (`$CASA_VPS_USUARIO_BILI`) nem do duplo-mcp): assim toda conversa fica à vista do dono, e cada pedido é uma tarefa com o tempo de ciclo medido.

O script é `scripts/linear-bili.sh` (nesta pasta). Ele usa o `dono.sh` da skill `linear` (a chave do dono no Keychain, nunca impressa), porque o Bili só reage quando uma **pessoa** o marca: o que o próprio app escreve não abre sessão.

## 1. Escolher o cartão

- **O pedido vai no cartão onde o assunto mora.** Procure antes (`S/projeto.sh` da skill `linear`): o cartão da frente, ou o cartão de conversa do marco.
- **Sem cartão, crie um** com a skill `linear` (um resultado, no projeto e no marco certos) e marque o Bili nele.
- **Uma sessão por cartão:** delegar o cartão ao Bili já abre uma sessão de agente dele, e uma menção depois abre outra, e as duas trabalham o mesmo cartão. Crie o cartão **sem delegado** e mande o pedido por uma menção, com o contexto inteiro; ou, se o cartão já está delegado, ponha o contexto no corpo e não o marque de novo até ele responder.
- **Comentário de projeto e de Doc ainda não chegam a ele** (falta o "Inbox notifications" do app e o tipo no duplo-server). Peça sempre num cartão.

## 2. Mandar

Escreva o pedido num arquivo do scratchpad (Markdown) e mande:

```sh
S=<pasta desta skill>/scripts/linear-bili.sh
sh $S pedir <TIME>-231 "$SCRATCH/pedido-bili.md"     # imprime "<id do comentário> <desde>"
```

- **Guarde o `<desde>`:** é o ponto a partir do qual se espera a resposta.
- **O script põe a menção** (`[@bili]($CASA_BILI_PERFIL_URL)`) no começo. Abra o texto com "(do Claude Code do Mac, pelo dono)", porque o comentário sai com o nome dele.
- **Monte o texto num arquivo, não num heredoc com chaves:** os hooks do repo da casa barram `{ ...; }`, `case` e `~` em variáveis no Bash.

## 3. Pedir trabalho

1. **Dê o contexto inteiro, porque ele não vê esta sessão:**
   - o objetivo;
   - o que já existe, com repo, caminho e **hash do commit**;
   - o que fazer, em passos;
   - como conferir;
   - as regras do dono (trabalhar direto no `main`, sempre commitar e sincronizar).
2. **Faça commit e push antes de mandar.** O Bili trabalha com os próprios clones na VPS, que podem estar atrás do `origin`. Mande o hash e peça um `git pull`.
3. **Aplicar na VPS fica com o Mac.** O Bili não tem sudo nem Docker lá. Mudança na máquina passa pelo repo da VPS (`$CASA_REPO_VPS`) (commit, depois o Ansible rodado do Mac). Peça para ele preparar, commitar e responder no cartão com o comando exato.
4. **Permissão do dono vai escrita no comentário** quando o pedido precisa dela (um merge, um deploy): "a permissão é minha".

## 4. Esperar e ler

```sh
sh $S esperar <TIME>-231 <desde> 900    # em segundo plano (run_in_background): sai no primeiro comentário dele (124 sem resposta)
sh $S ler <TIME>-231 6                  # os últimos 6 comentários do cartão
```

- No painel de agente do cartão, "📥 na fila" e "👀 vi, trabalhando" chegam em segundos; a resposta vem como comentário do Bili, com o rodapé `— ack: N s · ciclo: N s`. Passe o ciclo ao dono.
- **Confira que o pedido entrou, logo depois do `pedir`:** sem "📥 na fila" no painel em um minuto, olhe o último horário do stream ENTRADA (`curl -s "$CASA_NATS_MONITOR_URL/jsz?streams=true" | jq -r '.account_details[].stream_detail[] | select(.name=="ENTRADA") | .state.last_ts'`). Se ele for anterior ao seu `<desde>`, a entrega do Linear se perdeu e a sessão vai ficar "stale": marque-o de novo, com uma linha que aponta o pedido de cima.
- Um pedido grande pode passar dos 900 s: se o pedido entrou, rode o `esperar` de novo com o mesmo `<desde>`, sem comentar outra vez.
- Para acompanhar algo que já anda, comente uma pergunta curta no mesmo cartão ("em que pé está? poucas linhas") e espere.

## 5. Responder ao dono

Diga onde foi o pedido (o cartão, com o link) e o que o Bili respondeu, citado curto se ajudar. Não invente andamento: sem resposta ainda, diga que ele está trabalhando e que a espera segue. O que ele pedir de volta (aplicar o Ansible, um login, um sudo) é uma pendência sua ou do dono: diga de quem é.
