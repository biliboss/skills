---
name: bili
description: Hand a request to Bili, the owner's Hermes agent. On the Mac every request goes first to the local Bili (its pane, $CASA_BILI_LOCAL_PANE), after grilling the owner with AskUserQuestion; the local Bili does it, delegates to its subagents, or asks the VPS Bili through Linear (a mention on the card where the subject lives, never the Hermes API, SSH or duplo MCP). Also waits for and reads the VPS Bili's reply on the card. Use when the user says "pede pro bili", "manda pro bili", "roteia pro bili", "pergunta pro bili", "marca o bili", "o que o bili respondeu", "em que pé o bili está". Not `linear` (that edits Linear itself) nor `herdr-agentes` (other agent sessions in herdr) nor `delegate-and-review` (a subagent that opens a PR); this one asks the agent that keeps the memory.
metadata:
  version: 0.5.0
---

# bili — mandar um pedido ao Bili

## 0. No Mac: grill primeiro, depois o Bili local

Todo pedido do dono feito no Mac vai ao **Bili local** (o Hermes local, no pane `$CASA_BILI_LOCAL_PANE`). É ele quem faz, delega aos subagentes dele ou pede ao Bili da VPS pelo Linear (as seções 1 a 5, que ele mesmo usa). Uma sessão do Mac não chama o Bili da VPS direto.

1. **Grill antes de mandar, sempre, com a ferramenta AskUserQuestion.** Uma rodada de 1 a 4 perguntas sobre o que só o dono decide: o resultado esperado, o escopo (o que entra e o que fica de fora), quem faz e o limite (o que não pode ser tocado, o que precisa de OK). Cada pergunta com 2 a 4 opções concretas, a recomendada primeiro e marcada "(Recommended)", e o porquê em uma linha. O pedido já claro ainda passa por uma rodada curta, que confirma o resultado e o limite. Se a resposta trouxer dúvida nova, faça outra rodada antes de mandar.
2. **Escreva o pedido num arquivo** (o scratchpad, ou `~/.local/state/<tema>.md` quando for longo): o objetivo verificável, as decisões do grill com as respostas do dono, o contexto (repo, caminho, commit, cartão), o que não fazer e como responder (em até 5 linhas).
3. **Mande pela fila:** `sh <mux.sh da skill prime-agent> fila $CASA_BILI_LOCAL_PANE <arquivo>` (uma linha mandando ler o arquivo, quando ele for longo). `manda $CASA_BILI_LOCAL_PANE` só para corrigir o rumo do turno em curso; uma correção urgente, que não pode esperar o turno, vai como steer pelo `manda`.
4. **Junte o que chega junto:** vários pedidos numa mensagem numerada, nunca uma rajada de mensagens soltas.
5. **Arme o monitor do NATS** (se ainda não estiver de pé), pela ferramenta Monitor do Claude Code, com o tempo máximo:
   `uv run -q --script <pasta desta skill>/scripts/watch.py asks errors panes`
   Ele imprime uma linha por evento do NATS local que pede atenção humana, e cada linha vira um aviso na sessão: uma pergunta esperando o dono (`asks`), um erro de verdade (`errors`), um agente que parou ou travou (`panes`). Outros nomes: `cycle` (cada pedido respondido, com o lead time), `llm`, `routes`; `--list` mostra todos. O monitor expira (30 min no Claude Code): rearme quando o aviso de expiração chegar. Num terminal comum, o mesmo comando roda em primeiro plano.
   - **Um aviso é um fato, não uma resposta do dono:** passe ao dono só o que muda o que ele faria (uma pergunta para ele, um agente travado); o resto, ignore.
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
