---
name: herdr-mesa
description: Gerir a mesa local do herdr como um fluxo de fases, a partir de uma sessão gestora que só lê e move. Cada fase é um workspace (focus, backlog, working, ready to review, done today), cada item é uma aba, e os panes de um item andam juntos. No focus há um item só, com um cartão legível à esquerda (rich, escrito pela sessão do item) e o agente à direita. Use quando o dono disser "organiza o herdr", "gestão do herdr", "o que tem em cada workspace", "traz o próximo para o focus", "fecha esse e põe no done today", "move para working", "o cartão está ruim", "check all panes". Não é a `herdr-agentes` (abrir, mandar mensagem, fechar e retomar uma sessão) nem a `bili` (trabalho do Bili na VPS).
metadata:
  version: 0.1.0
---

# herdr-mesa — a mesa do herdr em fases

A sessão gestora organiza; as sessões dos itens trabalham. A gestora foca, lê os panes, move abas e fecha o que terminou. Ela não executa nem commita o trabalho de um item: quando algo precisa ser feito, manda a mensagem à sessão dona (`herdr-agentes`), com o sim e onde parar.

Scripts nesta pasta, sempre pelo caminho completo: `scripts/fase.sh` (mover entre fases) e `scripts/cartao.py` (o cartão, roda com `uv run`).

## O modelo

```
1 focus            um item só: [resumo / barra / agente | Bili]   o que o dono revisa agora
2 backlog          itens desligados (fichas) ou parados de propósito
3 working          itens trabalhando; o grupo junto (ex.: supervisora + Prime)
4 ready to review  itens que terminaram e esperam a vez no focus
5 done today       só o cartão dos itens fechados hoje
```

- **Item = aba.** O nome da aba é o tema do item; os panes dela são o grupo (a supervisora e os workers dela). Cada sessão com `/goal` próprio é um item à parte, para não esperar as outras.
- **O fluxo:** backlog → working → ready to review → focus (o dono revisa) → done today, ou de volta a working com a próxima tarefa.
- **Um item por vez no focus.** O próximo sobe do ready to review quando o dono fecha o atual.

## Passos

1. **Ver a mesa:** `fase.sh estado` (fases, itens e o `agent_status` de cada pane). Para ler um item, `herdr pane read <pane> --source recent-unwrapped --lines 60`.
2. **Montar, se faltar fase:** `fase.sh montar` cria os workspaces que faltam. O herdr não reordena workspaces: um criado depois vai para o fim. Para refazer a ordem, crie os workspaces na ordem e mova os itens para eles; o antigo fecha sozinho quando esvazia.
3. **Mover pelo estado:** `working` → `fase.sh mover <aba> working`; parou (`idle`, `done`) → `ready to review`; `blocked` (uma pergunta, que é do dono) → direto para o focus. Antes, confira o pane: um pi em `goal_wait` aparece como `done` mas espera outra sessão (a barra mostra "🎯 waiting"); ele fica no working.
4. **Trazer ao focus:** `fase.sh focar <aba>` monta a aba: o resumo em cima à esquerda (70% da altura), a barra (2 linhas) e o agente da frente embaixo (o worker à direita dele), e o Bili (o Hermes, achado pelo título ou por `MESA_BILI`) à direita, de cima a baixo, com 45% da largura para a esquerda. Se o item não tem `~/.local/state/<tema>.cartao.md`, peça à sessão dele que escreva (passo 6).
   - **O focus é do Bili, de forma contínua.** Ele sustenta o layout e gere os agentes: quando o agente da frente para, troca ou some, ele puxa o próximo, atualiza o resumo e devolve as proporções, sem ninguém pedir. Pergunta, aprovação ou `blocked` de qualquer agente: ele avisa o Gabriel na hora.
   - **A barra é o vigia do focus** (`scripts/barra.py`, no pane `barra`). Ela escreve o nome, o estado e o harness do agente da frente e devolve as proporções quando o agente troca. Quando ele para ou some, põe um aviso na fila do Bili (`mux.sh fila`). Com um `blocked` em qualquer pane da mesa, notifica o Gabriel (macOS) e o Bili. Cada aviso vai também a `mesa.focus.<evento>` no NATS.
5. **Fechar o item revisado:** primeiro traga o próximo ao focus (passo 4), depois `fase.sh concluir <aba>`: fecha os agentes (imprime o id para retomar), põe só o cartão no done today e fecha a aba. Na ordem inversa o focus esvazia, o herdr fecha o workspace e a ordem das fases se perde.
6. **O cartão:** a sessão do item escreve `~/.local/state/<tema>.cartao.md` ao parar, no estilo do `.wiki/escrever-bem.md` do repo da casa (frase curta, verbo forte, sem jargão de agente, o que importa primeiro). Ponha isto no briefing de toda sessão; o pedido pronto está em [references/cartao.md](references/cartao.md). Sem o arquivo, o cartão mostra o objetivo do briefing e a última fala crua do agente.

## Armadilhas

- **Desligue o vigia antigo** (`herdr-agentes/scripts/mesa.sh vigiar`) antes de organizar: ele move panes para abas "doing"/"review (N)" e desfaz as fases. Procure com `pgrep -fl 'mesa.sh vigiar'`; se uma sessão o religa, peça a ela que não religue.
- **O `pane_id` muda quando o pane troca de workspace, e o rótulo do pane se perde.** Ande pelo `terminal_id`, que fica, e renomeie de novo; o `fase.sh` já faz isso.
- **Workspace vazio fecha sozinho.** Nunca esvazie uma fase no meio de uma reorganização: leve o próximo antes de tirar o último.
- **No zsh, `set -- $x` não separa palavras.** Em laços de shell sobre "pane rótulo", use `${x%%:*}`/`${x##*:}` ou `IFS` com `read`.
- **A largura do pane vem do herdr** (`herdr pane layout`, o `rect.width` menos a borda): dentro do pane o `stty` e o `tput` não enxergam o tamanho, e o texto quebra em dobro.
- **O cartão é minimalista:** sem bordas, título em negrito, rótulos apagados. O pane do cartão mostra só o resumo; o nome e o estado do agente da frente ficam na barra, e os rótulos dos panes ficam limpos (`HNN - nome`), porque o `mux.sh` os lê. O herdr não reconhece o Hermes como agente: a barra e o cartão o chamam de `hermes` pelo título (⏳ = trabalhando).
- **O cartão redesenha num resize:** no SIGWINCH e quando a largura do pane muda (conferida a cada segundo), além da volta de 15 s; sem isso ele fica com a largura velha e o texto quebra torto.
- **Esperar é em segundo plano:** `herdr-events esperar <pane> --until idle,done,blocked` com `run_in_background`; laço com `sleep` em primeiro plano é barrado pelos hooks do Mac.
