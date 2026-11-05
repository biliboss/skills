---
name: herdr-agentes
description: Abrir, conduzir, fechar e retomar sessões de agente locais (Claude Code ou pi) nas abas do herdr do Mac, onde cada aba é uma fila de trabalho. Cobre criar um agente com nome, pôr em foco à direita, mover para uma aba, mandar uma mensagem ou um comando com barra (/goal, /rename, /reload), esperar, ler o pane, fechar e retomar pelo id da sessão. Use quando o dono disser "cria um agente", "novo agente no pi", "abre uma sessão para X", "põe em foco", "move para outra tab", "check pane", "manda reload", "fecha a tab", "fecha as outras", "retoma a sessão". Não é a `bili` (trabalho que o Bili faz na VPS, pedido por um cartão do Linear) nem a `delegate-and-review` (um subagente desta sessão que abre um PR).
metadata:
  version: 0.5.0
---

# herdr-agentes — as sessões locais, uma por aba

Cada aba do herdr no Mac é uma fila de trabalho: uma sessão de agente por frente, com o nome da frente. A sessão `bili` coordena, e as outras fazem. O script é `scripts/agente.sh` (nesta pasta); chame pelo caminho completo. A foto das sessões, para retomar, mora no `.wiki/herdr-sessoes.md` do repo da casa (`$CASA_REPO_PRINCIPAL`).

## 0. Local, Bili ou subagente?

| O trabalho | Vai para |
|---|---|
| Precisa do Mac (navegador do agente, arquivos locais, um login) ou o dono quer ver a sessão de perto | uma sessão local, por esta skill |
| Pode rodar sozinho na VPS e deixar o resultado num cartão | o Bili, por um cartão do Linear (skill `bili`) |
| Uma mudança de código com PR, revisada aqui | um subagente (skill `delegate-and-review`) |

## 1. Abrir

```sh
A=<pasta desta skill>/scripts/agente.sh
$A novo <tema> pi            # aba nova, pi com Opus medium (o padrão para agente de frente)
$A novo <tema> claude --foco # à direita deste pane, sem tirar o foco
$A novo <tema> pi --modelo claude-sonnet-5-5
$A novo <tema> pi --cwd <pasta> -- -ne -e <extensão.ts>   # outra pasta; o que vem depois de -- vai ao harness
```

Ele imprime o pane. O nome sai na aba, no pane e na sessão (`/rename` no Claude Code, `--name` no pi).

**Workspace novo com o Hermes** ("cria um workspace X e sobe o Hermes / o claude-mukutu lá"):

```sh
herdr workspace create --label <nome> --cwd <pasta>     # imprime root_pane e tab_id; sem --focus
herdr tab rename <tab> <nome>; herdr pane rename <pane> <nome>
herdr pane send-text <pane> 'hermes -p bili'; sleep 1; herdr pane send-keys <pane> Enter
herdr pane read <pane> --source recent --lines 30          # responda o prompt de abertura, se houver
```

- **"Hermes na conta mukutu" = `hermes -p bili`**: o perfil já fixa o `claude_config_dir` na `~/.claude-mukutu`. O alias `claude-mukutu` do zsh abre o **Claude Code**, não o Hermes; na dúvida entre os dois, o pedido do dono que diz "hermes" vence.
- **Leia o pane depois de abrir:** o Claude Code numa pasta nova para na pergunta de confiança (Esc sai sem criar sessão), e o Hermes pode abrir com uma pergunta (ex.: auto-prune; Enter adia). Só diga "pronto" quando aparecer o prompt.

- **Sem instrução**, quando o dono pedir "só com o nome": abra e pare aí.
- **Com tarefa:** escreva o briefing em `~/.local/state/<tema>.md` (objetivo verificável, contexto com repo e páginas do `.wiki`, limites, o que é do dono, como fechar). Depois mande o `/goal` com o detalhe no arquivo: `$A barra <pane> 'goal <resultado numa linha>. Detalhe e regras em ~/.local/state/<tema>.md'`.
- **Limites que vão em todo briefing:** trabalhar direto no `main` e sempre commitar e sincronizar; planejar primeiro escrevendo no `.wiki`; implementar com subagentes; Docker só se precisar, e no fim remover os containers e as imagens que ele criou (nunca `docker system prune`); segredo só pelo envless (`.wiki/segredos.md`).
- **Registre a sessão** numa linha da foto em `.wiki/herdr-sessoes.md` (tema, pane, harness, modelo, id), no mesmo commit.

## 2. Conduzir

```sh
$A manda <pane> <arquivo.md>   # uma mensagem; confere que o Enter submeteu
$A barra <pane> 'reload'       # comando com barra: a barra vai como tecla
herdr pane read <pane> --source recent --lines 40
herdr-events esperar <pane> --until idle,done,blocked --timeout 1800   # só com run_in_background
```

- **Esperar é sempre em segundo plano**, num comando só dele: os hooks do Mac barram um comando que espera em primeiro plano ou que junta `sleep` com um laço. A notificação chega quando a sessão para.

- **Mensagem longa vai por arquivo**, nunca pelo `send-text` direto: o texto colado vira "[Pasted text]", e o script reenvia o Enter até entrar.
- **Fila é o padrão; desviar o turno, só para corrigir o rumo.** O que não é urgente vai para a fila do agente (`mux.sh fila <id> <arquivo>` da skill `prime-agent`: Tab no Hermes). `manda` (Enter) faz o agente largar o turno em curso para ler a mensagem.
- **pi ocupado:** a mensagem vira "Steering" e entra quando ele terminar o turno; não mande de novo.
- **Digitando por script (`tmux send-keys`), pause ~1 s entre o texto e o Enter** e confira na tela que submeteu: um Enter colado ao texto vira quebra de linha ou se perde, e o comando fica parado na caixa.
- **Limpar a caixa de um agente** (um texto parado de um teste, um comando que não submeteu): `herdr pane send-keys <pane> ctrl+u` e confira com `herdr pane read`. O herdr usa nomes como `ctrl+u` e `esc`; os do tmux (`C-u`) ele recusa com `invalid_key`.
- **Depois de `/reload` no pi**, espere uns segundos antes da próxima mensagem: uma mensagem durante o reload se perde.
- **`done`/`idle` não quer dizer que parou:** um pi ou um Claude Code que só espera um subagente aparece como `done`/`idle` no herdr. Leia o rodapé do pane (`N running agent`, `live agents`, um `Agents` com spinner) antes de tratar como terminado, puxar o próximo ou avisar o dono.
- **Layout por script:** no `herdr pane split|move --ratio r`, o `r` é a fração que fica com o pane **original** (ou o alvo), e o novo vai à direita ou embaixo. O `pane resize` não encolhe um pane abaixo de umas 6 linhas: um pane curto (uma barra de 1 linha) tem de nascer curto. Crie o pane e mova o vizinho para baixo dele com `--split down --target-pane <curto> --ratio 0.02`. Depois de um `move`, renomeie o pane, porque o rótulo se perde. Confira sempre com `herdr pane layout --pane <p>` (os `rect`).
- **Pergunta da sessão (`blocked`)** é do dono. Você só responde por ele quando ele mandar.
- **Mover:** `herdr pane move <pane> --new-tab --no-focus` e `herdr tab rename <tab> <tema>`; para o foco, `herdr pane move <pane> --tab <tab> --split right --target-pane $HERDR_PANE_ID --no-focus`.

## 2b. O fluxo da mesa: backlog → preparing → doing → review

```sh
M=<pasta desta skill>/scripts/mesa.sh
$M organizar        # uma passada
$M vigiar 15        # em segundo plano (run_in_background), a cada 15 s
```

`mesa.sh` (ao lado do `agente.sh`) arruma as sessões pelo estado: quem está `working` vai para a aba **doing (N)**, lado a lado, com N = o WIP; quem parou (`idle`, `done`, `blocked`) vai para a aba **review (N)**, que é a fila de revisão do dono. A sessão do dono (o `$HERDR_PANE_ID` de onde a mesa é ligada, ou `MESA_DONO=<pane>`) nunca se move, e **nada fora do workspace dela é tocado**: uma sessão aberta noutro workspace do herdr fica onde está (o `MESA_WORKSPACE` troca o workspace). Os nomes das abas mudam com `MESA_ABA_TRABALHO` e `MESA_ABA_REVISAO`.

- **As quatro fases:** **backlog** (a sessão desligada, com a ficha), **preparing** (a aba do dono: o agente ao lado dele, montando o trabalho junto), **doing** (o agente segue sozinho) e **review** (parou; a fila de revisão humana). O vigia nunca mexe na aba do dono, então o que está em preparing fica ao lado até o dono soltar.
- **Puxar para preparing:** `backlog.sh puxar <tema>` retoma a sessão à direita do dono e tira a ficha (ela fica em `puxadas/`). Primeira mensagem: pedir onde parou e uma proposta de entrega, com o resultado verificável numa linha, **sem executar**. O dono dá o sim.
- **Soltar para doing:** depois do sim, `herdr pane move <pane> --tab <aba doing> --split right --target-pane <último pane dela> --no-focus` (ou o `/goal` e deixar o vigia levar, se a aba não for a do dono). A aba do dono volta a ter só a sessão dele.
- **Trabalho passado ao Bili:** quando a sessão local pede algo ao Bili (`linear-bili.sh pedir`, que imprime o `<desde>`), ela não fica esperando no foco. `bili-trabalho.sh acompanhar <tema> <cartão> <desde> claude|pi <id> "<o que conferir na volta>"` abre na doing um pane `bili: <tema>` que mostra ao vivo as atividades da sessão de agente do Bili no cartão, o tempo desde o pedido e desde a última atividade; depois `agente.sh fecha <pane>` fecha a sessão local. Quando o Bili responde no cartão, o pane vai para a review com a resposta, o ciclo e o que conferir; Enter retoma a sessão local para validar.
- **Desligar sem perder:** `backlog.sh guardar <tema> claude|pi <id|arquivo> "<o que é>" "<onde parou>" "<próximo passo>"` guarda a ficha e remonta a aba **backlog (N)**, antes da doing: uma grade igual (até 3 colunas), um pane por sessão, com o banner O QUE É / ONDE PAROU / PRÓXIMO. Enter no pane retoma a sessão ali mesmo; ela volta a trabalhar e a mesa a leva para a doing. `backlog.sh tirar <tema>` tira a ficha, `arrumar` remonta, `lista` mostra. Feche o pane do agente só depois de guardar a ficha, e escreva o próximo passo como uma ação, não como estado.
- **Revisou?** Feche com `agente.sh fecha <pane>` (o id vai para a foto) ou mande a próxima tarefa; a sessão volta a trabalhar e a mesa a leva de novo para a aba doing.

## 3. Fechar e retomar

```sh
$A foto                 # o que está aberto, com o id de cada sessão
$A fecha <pane>         # recusa se estiver working; imprime o id para retomar
$A novo <tema> claude --retoma <id>
$A novo <tema> pi --retoma <arquivo.jsonl> [--modelo M]
```

- **Antes de fechar:** a sessão parada (`idle`/`done`), o que ela escreveu commitado, e o id na foto do `.wiki/herdr-sessoes.md`. "Fecha as outras" quer dizer as sessões de trabalho; a sua e a que o dono nomeou ficam.
- **Limpar a mesa (fechar tudo fora do foco):** liste os panes de cada workspace (`herdr pane list`, com status e cwd). Para cada agente, leia o rodapé: um vigia em segundo plano ou um subagente vivo quer dizer que não parou, mesmo com `done`. Rode `git status` no cwd dele: mudança suja de dono desconhecido deixa aquele pane aberto, e você diz qual. Feche os agentes com `agente.sh fecha` (junte as linhas `retomar:` para a foto). Pane só de ficha ou de cartão sai com `herdr pane close`, depois de conferir que a ficha existe. Por fim, `herdr workspace rename` e `close` nos vazios, e uma seção na foto com tema, harness, id e onde parou.
- **O pi não guarda o modelo na sessão:** retome com o mesmo `--modelo` com que ela nasceu.
- **Teste descartável** (comparar extensões, modelos, um goal de brinquedo): `--cwd` numa pasta do scratchpad, para não sujar o repo, e `fecha` no fim.
- **O contexto que importa mora no `.wiki` e nas skills**, não no resume: uma sessão nova que lê o `.wiki` vale tanto quanto a retomada.
