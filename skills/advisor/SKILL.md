---
name: advisor
description: Use on every request before starting work, to decide whether to consult the advisor (a stronger session that only advises, reached by SendMessage with a shared context in ~/.local/share/advisor/) and to record that decision, called or not. The consult points are the plan before big work, when stuck, and before saying done; whether to call is read from the journal of past decisions of the same kind of task. Also covers the advisor's own side (how to answer). Triggers include "pergunta ao advisor", "plano antes de trabalho grande", "travei", "terminei, vou entregar", "você é o advisor". Not `delegate-and-review` (a subagent that opens a PR) nor `herdr-agentes` (opens another session); here the other session already exists and only gives the verdict.
metadata:
  version: 0.1.0
---

# advisor — o agente principal pergunta, o advisor aconselha

O padrão advisor: o agente principal (o Bili no Sonnet: atende o Gabriel, decide, delega e conduz as skills, mais barato e mais rápido) faz o trabalho; o advisor (Opus) é a segunda opinião para quando o julgamento pesa. Ele não executa nada: lê o contexto e devolve um conselho curto. O advisor **não vê a transcrição** do agente principal, então o contexto vive em `~/.local/share/advisor/` (`$ADVISOR_DIR`):

- `context.jsonl`: só recebe linhas novas, uma por evento `{id, at, actor, event, thread, value}`: `question.asked` (agente principal), `advice.given` (advisor) e `context.added` (qualquer um).
- `resources/<thread>/`: o que não cabe numa linha (diff, saída de teste, plano). Na linha vai só o caminho.
- `decisions.jsonl`: só recebe linhas novas; o diário de **chamar ou não chamar**, de onde o agente principal aprende quando vale a pena.
- `thread`: um slug curto por tarefa (`playground-absorver`), igual em todas as linhas dela.

Toda escrita é um script em `scripts/`, o caminho relativo à pasta da skill instalada (a que contém este `SKILL.md`; vale para os dois lados). O jq cuida do escape; montar o JSON à mão é onde o erro aparece. Variáveis: `ADVISOR_ACTOR` (quem escreve, padrão `agente`; ou `--actor`), `ADVISOR_TO` (o endereço do SendMessage, padrão `advisor`), `ADVISOR_DIR`.

## Antes de começar: chamar ou não

Faça isto em todo pedido que tem trabalho ou decisão pela frente. Uma consulta só ou um comando só não passa pelos pontos: responda e siga, sem gravar nada, ou o diário vira ruído. Quando a tarefa ou o dono pede o advisor, os pontos de consulta abaixo são obrigatórios e não há o que decidir. Nos outros pedidos, decida lendo o diário:

1. Dê um `task_kind` ao pedido, **um destes seis** (a lista é fechada: `codigo` e `código` fragmentariam o histórico): `codigo`, `delegacao` (fazer à mão ou delegar a um subagente local), `operacao-externa` (sai para fora ou não se desfaz), `ambiguidade`, `debug`, `pesquisa`.
2. Leia o que já se aprendeu, para cada ponto de consulta: `scripts/decisions.sh recent <task_kind> --moment <ponto>`. A chave é (`task_kind`, ponto): o plano costuma ouvir `segue` e é a checagem de entrega que pega as coisas, então as chamadas nunca se misturam entre pontos. Ele diz **CHAME** quando o conselho já mudou o rumo ou houve um `missed`, e **PULE** só com três chamadas avaliadas daquele tipo e ponto, nenhuma mudando o rumo. `irreversivel` nunca dá PULE. Pouco histórico é CHAME. Uma janela só de pulos volta a CHAME de propósito: pular se conquista com chamadas, nunca com mais pulos.
3. Em cada ponto de consulta, chamando ou não, grave a decisão com o motivo, **antes** de perguntar. Um pedido pode passar por vários pontos (`plano` e depois `irreversivel`): grave um por ponto, na mesma thread. O `decisions.sh` liga tudo pela thread, então `rate.sh` não repete o `task_kind`.
   `scripts/decide.sh <thread> --moment plano|travou|terminou|irreversivel|ambiguidade --called true|false --reason "..." --task-kind <kind>`
4. Depois da resposta do advisor: `scripts/rate.sh rated <thread> <id da pergunta> --moment <ponto> --changed-course true|false --useful true|false --note "..."`. O conselho mudou o que você fez? Valeu a chamada? Se você chamou, seguiu o conselho e deu errado, é um `rated` com `--useful false` e a nota do que faltou; o `missed` é só para quando **não** chamou.
5. Se você **não** chamou e depois deu errado (o dono corrigiu, um teste falhou): `scripts/rate.sh missed <thread> --moment .. --what "..."`, com o `--moment` em que a chamada teria ajudado. É o que impede o diário de ensinar a pular para sempre.

## Lado do agente principal

Os pontos de consulta são decisões, não só código. Fora deles, siga sozinho: é o ponto de usar o Sonnet.

1. **O plano** (`plano`): depois de se orientar e antes do trabalho grande, incluindo a escolha entre fazer à mão e delegar a um subagente local. "Este é o plano, está certo?"
2. **Travou** (`travou`): duas tentativas falharam, ou o caminho ficou ambíguo.
3. **Antes de entregar** (`terminou`): "isto cumpre o pedido? falta algo?". Quando se chama, é **mesmo com os testes verdes**; a saída dos testes vai como resource.
4. **Difícil de desfazer ou que sai para fora** (`irreversivel`): push na main, apagar, mandar mensagem a alguém, mexer num processo que não é seu.
5. **O pedido está ambíguo** (`ambiguidade`) e o task-understand não resolveu.

Os passos de cada consulta:

1. Ponha o que o advisor precisa em arquivos: o plano, o diff, a saída do teste.
2. Grave a pergunta (o script copia os arquivos para `resources/<thread>/` e imprime o id):
   `scripts/ask.sh ask <thread> --task "..." --goal "..." --done "..." --tried "..." --question "..." --resource <arquivo>`
   Os cinco campos são obrigatórios; sem eles a pergunta não vale. Quando o trabalho ainda nem começou, `--done "nada ainda"` e `--tried` com o plano.
3. Avise pelo SendMessage nativo: `to` = `$ADVISOR_TO` (padrão `advisor`), primeira linha `pergunta <id> na thread <thread>`. O texto da pergunta já está no contexto.
4. **Espere a resposta** antes de seguir naquele ponto. Passados uns 10 minutos sem resposta, siga e entregue dizendo "sem veredito do advisor".
5. Siga o veredito: `segue`; `corrige` (aplique a correção); `para` (pare e volte ao dono com o motivo). Se discordar, diga por quê em `--tried` na próxima pergunta. Nunca ignore em silêncio.
6. No fim, relate: quantas vezes consultou, o veredito de cada uma, se algum conselho mudou o que você fez e as linhas que a tarefa gravou em `decisions.jsonl` (`scripts/decisions.sh list <thread>`).

`scripts/ask.sh note <thread> "<fato>"` acrescenta um fato que vale para as próximas perguntas; `scripts/ask.sh thread <thread>` lê a thread.

## Lado do advisor

1. Leia a thread (`scripts/ask.sh thread <thread>`) e os `resources` citados, com os caminhos relativos a `~/.local/share/advisor/`. Pode ler o repositório, só leitura.
2. Não edite código, não rode nada que escreva, não faça o trabalho: aconselhe.
3. Grave a resposta: `scripts/ask.sh reply <thread> <id da pergunta> --verdict segue|corrige|para --advice "..." --risk "..."`. Conselho curto, até uns 15 linhas: o veredito, o próximo passo concreto e os riscos. Diga `para` quando o plano está errado.
4. Responda pelo SendMessage, `to` = o `from` da mensagem recebida, com o mesmo texto.

## Armadilhas

- **Linha curta nos jsonl** (até 3500 bytes): dois escritores acrescentando juntos só não se misturam com linhas pequenas. Os scripts recusam uma maior; o que é grande vai para um resource.
- **Segredo não vai**: o `ask.sh` recusa copiar `.env`, chaves, token e `.sesskey`, e mesmo assim não ponha um segredo no texto de um campo.
- **Os arquivos só crescem**: um erro numa linha se corrige com outra, nunca reescrevendo o `context.jsonl` nem o `decisions.jsonl`.
- **Pular sem registrar ensina errado**: grave a decisão também quando não chama, e o `missed` quando dá errado; sem eles o diário só conhece as chamadas.
- **Testar a skill**: `scripts/test.sh` roda tudo num diretório temporário. Para um teste à mão, use um `ADVISOR_DIR` temporário e confira só as linhas gravadas. Um subagente de teste que mande SendMessage para `advisor` sai com o endereço da sua sessão e chega ao advisor real como uma pergunta de verdade.
- **Pergunta sem contexto escrito não vale**: o advisor responde ao que está no contexto, não ao que você tem na cabeça.
