---
name: herdr-agentes
description: Abrir, conduzir, fechar e retomar sessões de agente locais (Claude Code ou pi) nas abas do herdr do Mac, onde cada aba é uma fila de trabalho. Cobre criar um agente com nome, pôr em foco à direita, mover para uma aba, mandar uma mensagem ou um comando com barra (/goal, /rename, /reload), esperar, ler o pane, fechar e retomar pelo id da sessão. Use quando o dono disser "cria um agente", "novo agente no pi", "abre uma sessão para X", "põe em foco", "move para outra tab", "check pane", "manda reload", "fecha a tab", "fecha as outras", "retoma a sessão". Não é a `bili` (trabalho que o Bili faz na VPS, pedido por um cartão do Linear) nem a `delegate-and-review` (um subagente desta sessão que abre um PR).
metadata:
  version: 0.3.1
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
- **pi ocupado:** a mensagem vira "Steering" e entra quando ele terminar o turno; não mande de novo.
- **Depois de `/reload` no pi**, espere uns segundos antes da próxima mensagem: uma mensagem durante o reload se perde.
- **Pergunta da sessão (`blocked`)** é do dono. Você só responde por ele quando ele mandar.
- **Mover:** `herdr pane move <pane> --new-tab --no-focus` e `herdr tab rename <tab> <tema>`; para o foco, `herdr pane move <pane> --tab <tab> --split right --target-pane $HERDR_PANE_ID --no-focus`.

## 2b. A mesa por estado: backlog, doing e review

```sh
M=<pasta desta skill>/scripts/mesa.sh
$M organizar        # uma passada
$M vigiar 15        # em segundo plano (run_in_background), a cada 15 s
```

`mesa.sh` (ao lado do `agente.sh`) arruma as sessões pelo estado: quem está `working` vai para a aba **doing (N)**, lado a lado, com N = o WIP; quem parou (`idle`, `done`, `blocked`) vai para a aba **review (N)**, que é a fila de revisão do dono. A sessão do dono (o `$HERDR_PANE_ID` de onde a mesa é ligada, ou `MESA_DONO=<pane>`) nunca se move, e **nada fora do workspace dela é tocado**: uma sessão aberta noutro workspace do herdr fica onde está (o `MESA_WORKSPACE` troca o workspace). Os nomes das abas mudam com `MESA_ABA_TRABALHO` e `MESA_ABA_REVISAO`.

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
- **O pi não guarda o modelo na sessão:** retome com o mesmo `--modelo` com que ela nasceu.
- **Teste descartável** (comparar extensões, modelos, um goal de brinquedo): `--cwd` numa pasta do scratchpad, para não sujar o repo, e `fecha` no fim.
- **O contexto que importa mora no `.wiki` e nas skills**, não no resume: uma sessão nova que lê o `.wiki` vale tanto quanto a retomada.
