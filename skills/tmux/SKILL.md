---
name: tmux
description: Faz tudo o que um agente precisa nos panes e janelas do tmux por scripts, sem montar comando na mão. Lê as últimas linhas de um pane, lista sessões, janelas e panes com comando e pasta, manda texto (inclusive um comando com barra para um Claude Code) com verificação antes do Enter, abre e renomeia janelas, e espera um pane mostrar um texto, com prazo. Use quando o dono disser "lê o pane", "manda para a janela", "abre uma janela no tmux", "espera o pane mostrar", "lista as janelas do tmux", "o que a janela bili-sonnet está mostrando", "renomeia a janela". Para abas e sessões do herdr use a `herdr-agentes`; esta é só do tmux.
metadata:
  version: 0.1.0
---

# tmux: panes e janelas por script

Toda necessidade de tmux de um agente passa por aqui, e quem precisar de algo novo evolui os scripts (e o `CHANGELOG.md`), em vez de improvisar. Scripts em `scripts/` (nesta pasta); chame pelo caminho completo. Nenhum script daqui mata sessão ou servidor.

Isto é para panes e janelas do **tmux**. As abas e sessões de agente do **herdr** são da skill `herdr-agentes`. O `prime-agent/scripts/mux.sh` continua como está.

## Alvos (o argumento `<alvo>`)

`%12` (id do pane) | `T02` (o id da casa, a opção `@tnn` do pane; fica quando o `%N` some) | `bili-sonnet` (nome da janela) | `main:3` ou `main:bili` (sessão:janela, nome ou índice) | `main:bili.1` (com o pane). A resolução é por **igualdade exata** e devolve um `%id`: `bili` nunca acerta `bili-sonnet`. Sem achar, ou com vários, o script falha e lista os candidatos (id, sessão:janela.pane, nome, comando). Janela com vários panes: vale o pane ativo.

## Comandos

```
scripts/win.sh list [--json]                       # quem existe: pane, sessão:janela.pane, janela, comando, pasta, ativo (*)
scripts/pane.sh read <alvo> [N=30] [--keep-blank]  # últimas N linhas sem brancos
scripts/pane.sh send <alvo> "<texto>" [--no-enter] [--timeout 5] [--no-verify]
scripts/pane.sh send <alvo> -- "-texto"            # texto que começa com -
scripts/pane.sh key  <alvo> Enter Escape C-c Down  # teclas nomeadas
scripts/pane.sh wait <alvo> --text '<regex>' --timeout 60
scripts/pane.sh wait <alvo> --idle 3 --timeout 60
scripts/win.sh new <nome> "<comando>" [--cwd DIR] [--session S] [--allow-duplicate]  # imprime o %id; não rouba o foco
scripts/win.sh rename <alvo> <novo-nome>
scripts/test.sh                                    # testa tudo num servidor privado
```

Códigos de saída: 0 ok, 124 prazo esgotado (`send` sem ver o texto, `wait`), 1 erro (alvo, tmux), 2 uso.

## Armadilhas, em cada passo

- **O alias.** No shell do dono, `tmux` é `tmux new-session -A -s main` e quebra qualquer subcomando (sem terminal, vira `open terminal failed: not a terminal`). Se for chamar o tmux à mão, use `command tmux`. Os scripts chamam o binário pelo caminho (`$TMUX_BIN`, senão `/opt/homebrew/bin/tmux`, senão `command -v tmux`). Nunca rode `tmux` sem caminho. `TMUX_SOCKET=nome` troca para outro servidor (`-L nome`): é como os testes ficam longe do servidor do dono.
- **`-t` explícito.** Sem `-t`, comandos como `display-message -p` falham fora de um terminal ("not a terminal") ou miram o pane errado. Os scripts passam sempre o `%id`; faça igual se chamar o tmux à mão. O `-t` do próprio tmux aceita prefixo (`bili` acertaria `bili-sonnet`), por isso a resolução é feita antes, por igualdade exata.
- **`send` = texto, conferir, Enter.** O texto vai com `send-keys -l` (literal), o script espera o FIM do texto aparecer no pane (até `--timeout`) e só então manda o Enter, em outra chamada. Texto e Enter na mesma chamada perdeu as primeiras letras de um comando com barra num Claude Code (`/reload-plugins` chegou `ad-plugins`). Se o fim não aparece, sai 124 sem Enter, com o texto talvez digitado: olhe com `read`, limpe com `key C-u`. Pane sem eco (senha) ou que redesenha o texto: use `--no-verify`.
- **Várias linhas.** Texto com quebra de linha vai por `load-buffer` + `paste-buffer -p -d` (com `send-keys -l` cada `\n` viraria Enter). Um TUI pode mostrar `[Pasted text ...]` em vez do texto: a conferência aceita esse marcador.
- **`--` antes de texto que começa com `-`.** `pane.sh send alvo -- "-n x"`; sem ele o texto seria lido como opção. O texto também pode vir por `--stdin`.
- **`wait` é um comando só, com prazo.** Ele repete a cada 0,2 s e sai sozinho; o prazo é obrigatório. Não escreva `while ... sleep` no comando do agente: os hooks desta máquina recusam (`no-sync-wait`). Pelo mesmo motivo chame os scripts pelo caminho completo, nunca por uma variável (o `var-command-guard` barra um programa rodado por variável), e sem `cd` antes. `--text` casa uma regex com as linhas atuais (já visíveis conta). `--idle S` espera a tela ficar parada S segundos e **não chega num Claude Code que está trabalhando** (o spinner muda a tela o tempo todo): ali use `--text`; com o TUI parado, o `--idle` sai 0.
- **`new` não rouba o foco** (`-d`) e recusa um nome já usado na sessão (igualdade exata), salvo `--allow-duplicate`. A pasta padrão é a do chamador.

## Evoluir

Mudou um script: rode `scripts/test.sh` (servidor privado, sai 0 só se tudo passa), anote no `CHANGELOG.md` e suba a versão. O teste não cobre um Claude Code de verdade; confira à mão um `send` de `/comando` num TUI, num servidor privado (`TMUX_SOCKET=nome`), nunca na janela de outro agente. Conferido na v0.1.0 com o Claude Code 2.1.318: `/reload-plugins` chega inteiro e executa, e um texto de duas linhas aparece digitado, sem Enter, com `--no-enter`.
