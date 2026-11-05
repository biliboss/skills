---
name: bili
description: Talk to Bili, the owner's long-lived Hermes agent on the VPS, through Linear — mention him on the card where the subject lives (that opens his agent session — duplo-server → NATS → Bili), wait for his reply on the card, read the thread, check how something is going. Linear is the only channel — never talk to Bili directly (no Hermes API, no SSH, no duplo MCP), and the Mattermost is off. Use when the user says "pede pro bili", "pergunta pro bili", "manda pro bili", "marca o bili", "manda um ping pro bili", "o que o bili respondeu", "em que pé o bili está". Not `linear` (that edits Linear itself — projects, cards, updates) nor `delegate` (another Claude Code session in a herdr pane) nor `delegate-and-review` (a subagent that opens a PR) — this one asks the agent that keeps the memory.
metadata:
  version: 0.4.4
---

# bili — falar com o Bili pelo Linear

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
5. **Dono de cada arquivo, antes de dividir:** quando o Mac (ou um subagente dele) e o Bili vão mexer no mesmo repo ao mesmo tempo, comente no cartão quem fica com quais arquivos ("você segue com X; eu crio Y e Z") antes de começar. Dois agentes na mesma página da wiki ou na mesma skill sobrescrevem o trabalho um do outro.
6. **Um lote de cartões (um goal) é um pedido por cartão**, cada um com o mesmo bloco comum (o goal, o que é Done ali — o Como conferir cumprido e o PR mergeado —, o WIP sem subcartão novo, os 4 casos do dono) mais uma linha só daquele cartão. Antes de mandar, conserte o quadro: Doing só o que alguém faz agora, e o marco certo.
7. **Uma série de ajustes ao mesmo pedido vai no mesmo cartão,** como comentários curtos que remetem ao de cima ("mais uma regra para o pedido de cima"), em vez de abrir outro cartão: o Bili junta tudo numa entrega só.

## 4. Esperar e ler

```sh
sh $S esperar <TIME>-231 <desde> 900    # em segundo plano (run_in_background): sai no primeiro comentário dele (124 sem resposta)
sh $S ler <TIME>-231 6                  # os últimos 6 comentários do cartão
```

- No painel de agente do cartão, "📥 na fila" e "👀 vi, trabalhando" chegam em segundos; a resposta vem como comentário do Bili, com o rodapé `— ack: N s · ciclo: N s`. Passe o ciclo ao dono.
- **Confira que o pedido entrou, logo depois do `pedir`:** sem "📥 na fila" no painel em um minuto, olhe o último horário do stream ENTRADA (`curl -s "$CASA_NATS_MONITOR_URL/jsz?streams=true" | jq -r '.account_details[].stream_detail[] | select(.name=="ENTRADA") | .state.last_ts'`). Se ele for anterior ao seu `<desde>`, a entrega do Linear se perdeu e a sessão vai ficar "stale": marque-o de novo, com uma linha que aponta o pedido de cima.
- Um pedido grande pode passar dos 900 s: se o pedido entrou, rode o `esperar` de novo com o mesmo `<desde>`, sem comentar outra vez.
- Para acompanhar algo que já anda, comente uma pergunta curta no mesmo cartão ("em que pé está? poucas linhas") e espere.
- **Acompanhar um lote:** um subagente por cartão, que só lê (estado, atividades, comentários, PR) e nunca faz o código. Se o cartão está parado há mais de 15 min, ele manda **um** `pedir` com o próximo passo concreto. Se a resposta do Bili traz um fato que já mudou (por exemplo, "a chave falta" quando ela já está no cofre), ele corrige no cartão, só com os nomes e nunca com os valores.
- **Antes de contar "N de M", confira o PR, não só o estado do cartão:** um PR mergeado cujo Done era o merge fecha o cartão. Mova-o com "Decidi mover para Done porque…"; o Bili nem sempre move.

## 5. Responder ao dono

Diga onde foi o pedido (o cartão, com o link) e o que o Bili respondeu, citado curto se ajudar. Não invente andamento: sem resposta ainda, diga que ele está trabalhando e que a espera segue. O que ele pedir de volta (aplicar o Ansible, um login, um sudo) é uma pendência sua ou do dono: diga de quem é.

- **Trava técnica não é pendência do dono.** Quando o bloqueio é um ruleset, uma permissão ou uma configuração (por exemplo, um PR com REVIEW_REQUIRED por um ruleset que exige code owner), diga a trava pelo nome (`gh api repos/<o>/<r>/rulesets`) e proponha tirá-la ou contorná-la. "Espera o dono" só vale para dinheiro, login ou conta, publicar para fora e apagar; escrito fora desses casos, o cartão fica parado sem que ninguém decida.
- **Aplicar o Ansible do Mac por um stack só:** rode `--check --diff` primeiro. Se ele falha num stack que não é o do pedido (um `.env` que falta em outro serviço), restrinja à lista de stacks em vez de parar: `-e '{"stacks":["<nome>"]}'`. Aplique só se o diff tocar apenas o stack pedido, e confira o serviço ao vivo (um pedido válido aceito, um inválido recusado) antes de fechar o cartão.
