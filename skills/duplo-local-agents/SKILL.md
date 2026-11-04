---
name: duplo-local-agents
description: Abrir, conduzir, fechar e retomar sessões de agente locais (Claude Code, pi, Hermes, Prime Agent) em panes do herdr, do tmux ou sem multiplexador, e organizar a mesa em fases com o focus (herdr). O mux.sh é a única porta para um pane (panes, abrir, ler, tecla, manda, fila, barra, nomear, fecha). Use quando o dono disser "cria um agente", "novo agente no pi", "abre uma sessão para X", "manda para o H05", "lê o T01", "check pane", "manda reload", "fecha a tab", "retoma a sessão", "organiza o herdr", "traz o próximo para o focus", "move para working", "o cartão está ruim". Não é a `bili` (trabalho do Bili na VPS, por cartão do Linear) nem a `delegate-and-review` (subagente desta sessão que abre PR).
metadata:
  version: 1.0.0
---

# duplo-local-agents — as sessões locais, em qualquer multiplexador

Uma sessão de agente por frente, num pane com id e nome. A sessão `bili` (H00) coordena e as outras fazem. **Só o `scripts/mux.sh` fala com um pane**: não chame `herdr pane ...` nem `tmux send-keys` para mandar, ler ou fechar. Nesta pasta, `S` = `scripts/` (chame pelo caminho completo; nenhum script lê stdin).

O que é do herdr (abas, workspaces, mover panes, a mesa em fases, o `esperar`) está em `S/herdr/` e na seção **SOMENTE HERDR** abaixo. Sem herdr nem tmux, `mux.sh abrir` imprime o comando para rodar num terminal à parte (sai com 3).

## 0. Local, Bili ou subagente?

| O trabalho | Vai para |
|---|---|
| Precisa do Mac (navegador do agente, arquivos locais, um login) ou o dono quer ver a sessão de perto | uma sessão local, por esta skill |
| Pode rodar sozinho na VPS e deixar o resultado num cartão | o Bili, por um cartão do Linear (skill `bili`) |
| Uma mudança de código com PR, revisada aqui | um subagente (skill `delegate-and-review`) |

## 1. O `mux.sh`

```sh
M=<pasta desta skill>/scripts/mux.sh
sh $M qual                       # herdr, tmux ou nenhum
sh $M panes                      # id, mux, pane, nome, estado (todos os panes dos dois)
sh $M abrir <pasta> <nome> <cmd> # pane à direita deste, sem foco; imprime o id
sh $M ler <pane> [linhas]        # a tela
sh $M tecla <pane> Enter         # uma tecla (Down, Escape, C-o)
sh $M manda <pane> <arquivo>     # uma mensagem; reenvia o Enter se a caixa ficou com "[Pasted text"
sh $M fila <pane> <arquivo>      # como manda, mas na fila do agente (Tab no Hermes)
sh $M barra <pane> 'reload'      # comando com barra: a barra vai como tecla
sh $M nomear <pane> <nome> [ID]  # "ID - nome"
sh $M fecha <pane>               # no herdr recusa se o agente estiver working
sh $M papeis                     # os papéis da mesa, lidos do mesa.toml
```

- **Ids:** `TNN` no tmux (opções `@tnn`/`@nome` do pane, porque o Claude Code sobrescreve o título) e `HNN` no herdr (rótulo `HNN - nome`). `<pane>` aceita o id ou o id nativo (`%4`, `w5R:p39`). O multiplexador de `abrir` vem de `$MUX`, senão de `$HERDR_PANE_ID`/`$TMUX`.
- **Mensagem longa vai por arquivo**, nunca colada direto: o texto colado vira "[Pasted text]".
- **Papéis e multiplexador padrão vêm do `mesa.toml`** (`~/biliboss/dev/prime-bili/scripts/mesa.toml`, ou `$MESA_TOML`; spec em `~/biliboss/scripts/mesa.md`; `just -f ~/biliboss/dev/prime-bili/justfile mesa-config` imprime a config). `<pane>` aceita também o papel (`human`, `router`, `coordinator`), que vira `<mux>:<id>` (`router = "none"`: sem pane, erro claro); um id sem prefixo vai para o multiplexador de `[roles].agents`; e sem `$MUX`, `$HERDR_PANE_ID` nem `$TMUX`, `qual` usa o de `[roles].agents` se estiver no ar. Sem o arquivo (ou sem python >= 3.11), vale o comportamento de sempre. Não há cópia da config aqui.
- **Outro multiplexador** entra como um ramo novo no `mux.sh`, com os mesmos verbos.
- **No REPL do Prime Agent** a skill Python `mux` (`prime-agent/python/mux`) embrulha este mesmo `mux.sh`.
- **No tmux, ligue `set -g extended-keys on`** no `~/.tmux.conf`, senão o Enter com modificador falha.

## 2. Abrir

```sh
A=<pasta desta skill>/scripts/agente.sh
sh $A novo <tema> pi             # pane à direita, pi com Opus medium (padrão de agente de frente)
sh $A novo <tema> claude
sh $A novo <tema> pi --modelo claude-sonnet-5-5
sh $A novo <tema> pi --cwd <pasta> -- -ne -e <extensão.ts>   # o que vem depois de -- vai ao harness
sh $A novo <tema> pi --aba       # SOMENTE HERDR: numa aba própria
```

Imprime o id (HNN/TNN). O nome sai no pane e na sessão (`/rename` no Claude Code, `--name` no pi).

- **Sem instrução** ("só com o nome"): abra e pare.
- **Com tarefa:** escreva o briefing em `~/.local/state/<tema>.md` (objetivo verificável, contexto com repo e páginas do `.wiki`, limites, o que é do dono, como fechar, e o pedido do `<tema>.cartao.md` de `.wiki/herdr-focus.md`). Depois: `sh $A barra <id> 'goal <resultado numa linha>. Detalhe e regras em ~/.local/state/<tema>.md'`.
- **Limites em todo briefing:** direto no `main`, sempre commitar e sincronizar; planejar escrevendo no `.wiki`; implementar com subagentes; Docker só se precisar e, no fim, remover o que criou (nunca `docker system prune`); segredo só pelo envless (`.wiki/segredos.md`).
- **Registre a sessão** numa linha da foto em `.wiki/herdr-sessoes.md` (tema, pane, harness, modelo, id), no mesmo commit.

## 3. Conduzir

```sh
sh $A manda <id> <arquivo.md>
sh $A barra <id> 'reload'
sh $M ler <id> 40
```

- **Esperar é sempre em segundo plano**, num comando só dele (os hooks do Mac barram espera em primeiro plano ou `sleep` em laço). No herdr: `herdr-events esperar <pane> --until idle,done,blocked --timeout 1800` com `run_in_background`. No tmux não há estado: confira com `mux.sh ler` em chamadas separadas.
- **pi ocupado:** a mensagem vira "Steering" e entra no fim do turno; não mande de novo.
- **Depois de `/reload` no pi**, espere uns segundos: uma mensagem durante o reload se perde.
- **Pergunta da sessão (`blocked`)** é do dono; você só responde por ele quando ele mandar.

## 4. Fechar e retomar

```sh
sh $A foto                       # o que está aberto (e, no herdr, o id da sessão)
sh $A fecha <id>                 # recusa se working; no herdr imprime "retomar: ..."
sh $A novo <tema> claude --retoma <id>
sh $A novo <tema> pi --retoma <arquivo.jsonl> [--modelo M]
```

- **Antes de fechar:** sessão parada, o que escreveu commitado, e o id na foto de `.wiki/herdr-sessoes.md`. "Fecha as outras" = as sessões de trabalho; a sua e a que o dono nomeou ficam.
- **O pi não guarda o modelo na sessão:** retome com o mesmo `--modelo`.
- **Teste descartável:** `--cwd` numa pasta do scratchpad e `fecha` no fim.
- **O contexto que importa mora no `.wiki` e nas skills**, não no resume.

## SOMENTE HERDR — a mesa em fases e o focus

A regra, o layout, o KV `mesa_focus` e o formato do cartão estão em `.wiki/herdr-focus.md` do repo da casa; **não há cópia aqui**. O card e a title-bar são do `dev/prime-bili` (`scripts/card.py`, `scripts/title_bar.py`) e rodam por `just -f ~/biliboss/dev/prime-bili/justfile card|title-bar|focus-set|focus-check`.

A sessão gestora só lê e move; quando algo precisa ser feito, manda a mensagem à sessão dona (seção 3). Fases (workspaces): `focus`, `backlog`, `working`, `ready to review`, `done today`; item = aba (os panes dela andam juntos). Fluxo: backlog → working → ready to review → focus (o dono revisa) → done today, ou de volta a working. Script: `S/herdr/fase.sh` (`estado`, `montar`, `mover <aba> <fase>`, `focar <aba>`, `concluir <aba>`).

1. **Ver:** `fase.sh estado`; para ler um item, `mux.sh ler <id> 60`.
2. **Montar o que falta:** `fase.sh montar`. O herdr não reordena workspaces: para refazer a ordem, crie na ordem e mova os itens.
3. **Mover pelo estado:** working → `mover <aba> working`; parou (`idle`, `done`) → `ready to review`; `blocked` (pergunta do dono) → focus. Um pi em `goal_wait` aparece como `done` mas espera outra sessão: fica no working.
4. **O focus tem sempre 4 panes fixos:** card, title-bar, o agente da frente e o H00. É para o item que precisa do Gabriel; agente que trabalha sozinho vai para o working. `focar <aba>` com o focus vazio monta; com o focus montado é uma **troca**, nunca um pane novo: o agente da frente vai para o working (ainda trabalha) ou o backlog (com ficha), o novo entra embaixo do card (split down, ratio 0.7), a aba do focus é renomeada, e grava `focus-set --current <tema> --pick-next` (sem `--pick-next` no `focus_set.py`, vai `--next`). O card e a title-bar não reiniciam (leem o `mesa_focus`). No fim roda `focus-check`, se a receita existir. O ratio mínimo do herdr é 0.1: a title-bar fica com cerca de 6 linhas numa aba de 60; não tente menos.
5. **O H00 sustenta o focus** de forma contínua e avisa o Gabriel na hora de pergunta, aprovação ou `blocked`.
6. **Fechar o item revisado:** primeiro `focar` o próximo, depois `fase.sh concluir <aba>` (fecha os agentes, imprime o id para retomar, deixa só o cartão no done today). Na ordem inversa o focus esvazia e o herdr fecha o workspace.
7. **O cartão** é do `~/.local/state/<tema>.cartao.md`, escrito pela sessão do item ao parar (estilo de `.wiki/escrever-bem.md`). Ponha o pedido em todo briefing.
8. **Backlog e Bili em acompanhamento:** `S/herdr/backlog.sh` (fichas das sessões desligadas) e `S/herdr/bili-trabalho.sh` (trabalho passado ao Bili, na aba doing); ambos só herdr. O antigo `mesa.sh vigiar` saiu: se um ainda rodar (`pgrep -fl 'mesa.sh vigiar'`), desligue, senão ele desfaz as fases.

Armadilhas do herdr:

- **No herdr 0.9.3, o `send-keys` usa `ctrl+u` (limpa a caixa) e `esc`; `C-u` dá erro.** Pelo `mux.sh tecla`, passe esses nomes.
- **O `osascript` (System Events) perde as janelas do Chrome quando a tela do Mac bloqueia** (o processo da frente vira o loginwindow), e o cua-driver pode falhar em capturar (`could not create image from display`). Espere a tela voltar ou peça o clique ao dono.
- **O `pane_id` muda quando o pane troca de workspace e o rótulo se perde:** ande pelo `terminal_id` (o `fase.sh` já faz) e renomeie de novo.
- **Workspace vazio fecha sozinho:** leve o próximo antes de tirar o último.
- **No zsh, `set -- $x` não separa palavras:** use `${x%%:*}`/`${x##*:}` ou `IFS` com `read`.
- **A largura do pane vem do herdr** (`herdr pane layout`); dentro do pane `stty`/`tput` não a enxergam.
- **O herdr não reconhece o Hermes como agente:** o card o chama de `hermes` pelo título.
