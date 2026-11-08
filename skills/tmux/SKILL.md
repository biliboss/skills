---
name: tmux
description: >-
  Faz tudo o que um agente precisa no tmux por scripts, sem montar comando na mão: lê as últimas linhas de um pane, lista sessões, janelas e panes, manda texto (inclusive comando com barra para um Claude Code) com verificação antes do Enter, abre e renomeia janelas, espera um pane mostrar um texto, com prazo. E roda processo longo (servidor, watcher, suite de testes) numa sessão tmux nomeada presa à worktree do dono, com log, vaga global para testes e limpeza de órfão, nunca solto em segundo plano. Use quando o dono disser "lê o pane", "manda para a janela", "abre uma janela no tmux", "espera o pane mostrar", "lista as janelas do tmux", "renomeia a janela", "sobe o servidor", "roda os testes em tmux", "processo órfão", "mata o que ficou rodando", "o watcher ficou rodando". Para abas e sessões do herdr use a `duplo-local-agents`; esta é só do tmux.
metadata:
  version: 0.6.2
---

# tmux: panes e janelas por script

Toda necessidade de tmux de um agente passa por aqui, e quem precisar de algo novo evolui os scripts (e o `CHANGELOG.md`), em vez de improvisar. Scripts em `scripts/` (nesta pasta); chame pelo caminho completo. Só o `run.sh` mata, e só sessão que ele mesmo criou (marcada); nunca o servidor.

Isto é para panes e janelas do **tmux**. As abas e sessões de agente do **herdr** são da skill `duplo-local-agents`, que também fala com o tmux pelo `mux.sh` dela.

## Alvos (o argumento `<alvo>`)

`%12` (id do pane) | `T02` (convenção opcional da casa: a opção `@tnn` do pane, que fica quando o `%N` some; sem a opção, o alvo cai na regra do nome) | `bili-sonnet` (nome da janela) | `main:3` ou `main:bili` (sessão:janela, nome ou índice) | `main:bili.1` (com o pane). A resolução é por **igualdade exata** e devolve um `%id`: `bili` nunca acerta `bili-sonnet`. Sem achar, ou com vários, o script falha e lista os candidatos (id, sessão:janela.pane, nome, comando). Janela com vários panes: vale o pane ativo.

## Comandos

```
scripts/win.sh list [--json]                       # quem existe: pane, sessão:janela.pane, janela, comando, pasta, ativo (*)
scripts/pane.sh read <alvo> [N=30] [--keep-blank]  # últimas N linhas sem brancos
scripts/pane.sh send <alvo> "<texto>" [--no-enter] [--timeout 5] [--no-verify]
scripts/pane.sh send <alvo> -- "-texto"            # texto que começa com -
scripts/pane.sh key  <alvo> Enter Escape C-c Down  # teclas nomeadas
scripts/pane.sh wait <alvo> --text '<regex>' --timeout 60
scripts/pane.sh wait <alvo> --idle 3 --timeout 60
scripts/pane.sh do   <alvo> k=f t='texto' k=Enter s=0.6 --read 20   # um tiro: teclas, texto e pausas em ordem, depois o pane
scripts/win.sh new <nome> "<comando>" [--cwd DIR] [--session S] [--allow-duplicate]  # imprime o %id; não rouba o foco
scripts/win.sh rename <alvo> <novo-nome>
scripts/run.sh start|ls|log|stop|reap ...                # processo longo em sessão nomeada: veja "Processos longos"
scripts/test.sh                                    # testa tudo num servidor privado
```

Códigos de saída: 0 ok, 124 prazo esgotado (`send` sem ver o texto, `wait`), 1 erro (alvo, tmux), 2 uso.

## Armadilhas, em cada passo

- **Leia o pane antes de mandar tecla.** Uma janela que você abriu pode ter virado do dono: ele entra nela e o agente dela (uma TUI do Hermes, um Claude Code) passa a ser a conversa dele, às vezes a mesma em que você roda. Antes de `send` ou `key`, `read` o pane: se há um agente vivo (prompt de TUI, barra de status, turno em curso), não mande comando de sair (`/quit`, `/exit`, `C-c`, `C-d`) nem um comando de shell, porque vira mensagem ou fecha a sessão dele. Para reabrir, abra uma janela nova (`win.sh new`) e deixe a antiga para ele.
- **O alias.** No shell do dono, `tmux` é `tmux new-session -A -s main` e quebra qualquer subcomando (sem terminal, vira `open terminal failed: not a terminal`). Se for chamar o tmux à mão, use `command tmux`. Os scripts chamam o binário pelo caminho (`$TMUX_BIN`, senão `/opt/homebrew/bin/tmux`, senão `command -v tmux`). Nunca rode `tmux` sem caminho. `TMUX_SOCKET=nome` troca para outro servidor (`-L nome`): é como os testes ficam longe do servidor do dono.
- **`-t` explícito.** Sem `-t`, comandos como `display-message -p` falham fora de um terminal ("not a terminal") ou miram o pane errado. Os scripts passam sempre o `%id`; faça igual se chamar o tmux à mão. O `-t` do próprio tmux aceita prefixo (`bili` acertaria `bili-sonnet`), por isso a resolução é feita antes, por igualdade exata.
- **`send` = texto, conferir, Enter.** O texto vai com `send-keys -l` (literal), o script espera o FIM do texto aparecer no pane (até `--timeout`) e só então manda o Enter, em outra chamada. Texto e Enter na mesma chamada perdeu as primeiras letras de um comando com barra num Claude Code (`/reload-plugins` chegou `ad-plugins`). Se o fim não aparece, sai 124 sem Enter, com o texto talvez digitado: olhe com `read`, limpe com `key C-u`. Texto longo num TUI que quebra a linha (o Claude Code quebra em ~85 colunas) faz a conferência falhar mesmo com o texto inteiro digitado, porque o fim aparece partido entre duas linhas: `read` o pane e, se o texto está todo lá, mande só `key <alvo> Enter`; não reenvie, que duplica. Pane sem eco (senha) ou que redesenha o texto: use `--no-verify`.
- **Responder um menu de escolha num TUI** (a pergunta do Claude Code, com `❯` na opção marcada): `read` o pane, ache a linha do `❯` e a opção que você quer, mande `key <alvo> Up` ou `Down` uma vez por linha, `read` de novo e confira que o `❯` está na opção certa, e só então `key <alvo> Enter`. O cursor não começa sempre na primeira opção, e um número digitado pode cair na linha de texto livre. Quem escolhe é quem tem o aval: só responda um menu que caiba nas decisões do agente (fora dinheiro, login, publicar para fora e apagar).
- **Uma interação de TUI é um tiro só: `pane.sh do`.** Tecla que muda de modo, texto, Enter e a leitura do que a tela fez vão numa chamada (`k=f t='feedback' k=Enter --read 12`), com um respiro de 0,15 s entre os passos e 0,5 s antes de ler; `s=<seg>` acrescenta uma pausa. Não confere o texto como o `send`: use para uma TUI sua (atalhos de uma tecla, um input que você conhece); para o prompt de outro agente, `send`.
- **Várias linhas.** Texto com quebra de linha vai por `load-buffer` + `paste-buffer -p -d` (com `send-keys -l` cada `\n` viraria Enter). Um TUI pode mostrar `[Pasted text ...]` em vez do texto: a conferência aceita esse marcador.
- **`--` antes de texto que começa com `-`.** `pane.sh send alvo -- "-n x"`; sem ele o texto seria lido como opção. O texto também pode vir por `--stdin`.
- **`wait` é um comando só, com prazo.** Ele repete a cada 0,2 s e sai sozinho; o prazo é obrigatório. Não escreva `while ... sleep` no comando do agente: os hooks desta máquina recusam (`no-sync-wait`). Pelo mesmo motivo chame os scripts pelo caminho completo, nunca por uma variável (o `var-command-guard` barra um programa rodado por variável), e sem `cd` antes. `--text` casa uma regex com as linhas atuais (já visíveis conta). `--idle S` espera a tela ficar parada S segundos e **não chega num Claude Code que está trabalhando** (o spinner muda a tela o tempo todo): ali use `--text`; com o TUI parado, o `--idle` sai 0.
- **Mover janela não manda tecla.** Para reorganizar sessões e abas (`command tmux move-window -s main:1 -t bili:0`, `swap-window`, `rename-window`) o agente vivo dentro dela segue no mesmo turno: é o jeito seguro de mexer no layout do dono. Abas numeradas 1..N sem buraco: `set -g renumber-windows on` (servidor vivo e `~/.tmux.conf`) só age quando uma janela fecha; depois de `new-window -a` ou `move-window -a/-b`, que empurram índices, rode `command tmux move-window -r -t =<sessão>` para fechar os buracos. Fechar (`kill-window`) só a janela ociosa (`read` mostra o prompt parado, sem turno) e com o pedido dele.
- **`swap-window` sem `-d` para não roubar o foco.** No tmux 3.7 o `-d` faz a janela movida virar a atual (o contrário do que o man sugere): um swap com `-d` tira o dono da aba dele. Sem `-d` o foco fica onde estava. Confira num servidor privado (`list-windows -F '#{window_index}:#{window_name}#{?window_active,*,}'`) antes de confiar no flag.
- **Estado ao vivo do tmux: publique na escrita, não assine.** As assinaturas do control mode (`refresh-client -B`, `%subscription-changed`) avisam no máximo 1 vez por segundo (man tmux); para menos de 50 ms, quem grava a opção (`set-option @x`) publica o evento no mesmo passo. Num gancho quente, cada processo custa ~10-15 ms no macOS carregado: monte o JSON com `printf -v` (sem `$(...)`), leia a janela numa chamada só (`display-message -p -t <alvo> '<formato com várias opções>'`) e fale com o NATS pelo `/dev/tcp` do bash (`CONNECT {}`, `PUB <assunto> <bytes>`, `PING`, espere `PONG`) em vez de abrir o CLI `nats`. Meça com `$EPOCHREALTIME` (bash 5), não com `perl`/`date`, que somam o próprio fork.
- **Sessão nunca tem ponto no nome.** O tmux lê o ponto como janela.pane até com `=` (`has-session -t '=sygnal 0.2'` dá "can't find pane: 2"), então o `sesh connect`/`sesh last` dos atalhos do dono não chega nela e o atalho "não funciona". Ao criar ou renomear, troque o ponto por hífen; achou uma assim, `rename-session -t '$<id>' '<nome-com-hífen>'` (e a janela e o `@thread` junto), sem respawn: o agente dentro segue.
- **"O atalho não funciona": siga a cadeia.** Tecla do Ghostty (`grep keybind ~/.config/ghostty/config`, ex. `cmd+o=text:\x02o`) → binding do tmux (`list-keys | grep -iE 'sesh|switch-client'`) → rode o comando de baixo à mão com o alvo que falha (`has-session -t '<nome>'`). O erro aparece no último elo, quase sempre o nome.
- **Nome com ponto ou espaço nunca é alvo; use o id.** No `-t`, o ponto separa o pane: `=sygnal 0.2:_p` é lido como outra coisa e o comando acerta outra janela (um `kill-window` assim derrubou o agente vivo de outra aba). Pegue os ids ao criar (`new-session -d -P -F '#{session_id}'`, `new-window -P -F '#{window_id}'`) e mire `$N`/`@N`; ao listar, separe por `|`, nunca por espaço. Antes de qualquer `kill-window` fora de teste, confira com `display-message -p -t <alvo> '#{window_name}'` que o alvo é a janela que você criou. **Derrubou a aba de um agente por engano:** a conversa está no disco; ache-a pelo `.jsonl` mais recente (`ls -t ~/.claude/projects/*/*.jsonl`, e `~/.claude-*/projects` para outra conta), descarte as que ainda estão vivas em outro pane (`capture-pane -S -200` e procure a última mensagem do dono daquele arquivo), e reabra numa janela nova na pasta do projeto com `claude --dangerously-skip-permissions --resume <id>` (ou `hermes -p <perfil> --resume <id>`); diga ao dono que um turno em curso parou e precisa ser pedido de novo.
- **"Cadê a sessão X" não é "X morreu".** Um agente aberto por `zsh -c 'hermes …; exec zsh'` mostra `zsh` em `#{pane_current_command}`, mas segue vivo. Antes de reabrir, confira `ps -axo pid,command | grep <título ou id>` e `pane.sh read <alvo>` (barra `ready`, prompt). Vivo: "reabrir" pedido pelo dono é levar o cliente dele até lá, `switch-client -c <tty do cliente> -t '$<id da sessão>'` (o tty sai de `list-clients`), sem respawn, que mataria o turno. Ache-o também pelo nome atual no `sesh list`: o nome pode ter mudado (espaço e ponto no lugar do hífen). Só mova o foco do dono quando ele pediu.
- **Opção de SESSÃO precisa de `:` no alvo.** `set-option -t =<sessão> @x v` falha com "no such session" (o `=nome` sem `:` é lido como janela); use `-t "=<sessão>:"` em `set-option` e `show-options -qv`. `list-windows -t =<sessão>` funciona sem o `:`.
- **`new` não rouba o foco** (`-d`) e recusa um nome já usado na sessão (igualdade exata), salvo `--allow-duplicate`. A pasta padrão é a do chamador.

## Processos longos

**Regra:** servidor, watcher e suite de testes nunca vão para `run_in_background`, `&` ou `nohup`. Vão por `scripts/run.sh start`, que os põe numa sessão tmux com o nome da **worktree** do trabalho (o dono observável: num Claude Code o subagente roda dentro do processo do pai, então a worktree é o que vive e morre com a tarefa). O dono os vê no tmux/sesh (⌘O), e a sessão acaba quando a worktree acaba. Motivo: um watcher de testes órfão rodou 1h36 em laço depois que o pai morreu (load average 165).

- **Testes:** `--low --slot`. `--low` roda sob `taskpolicy -b` (QoS de fundo do macOS; sem ele, `nice -n 10`); `--slot` espera uma das `PROCS_MAX_SLOTS` vagas globais (padrão 2), a tampa da máquina inteira para suites.
- **Resultado:** `run.sh log <sessão>:<nome>`. Nunca rode a suite de novo só para ver o resultado: o log termina com `exit=<código>` (0 passou, outro falhou; sem essa linha ainda roda ou foi morto).
- **Fim:** quando o comando acaba a janela fica aberta mostrando `exit=N` (Enter fecha); sessão morta por `stop` ou `reap` não deixa a linha `exit=`.

```
scripts/run.sh start <nome> [--cwd DIR] [--owner DIR] [--low] [--slot] [--restart] -- <comando...>
scripts/run.sh ls [--json]                  # sessões do run.sh: dono, se a pasta existe, janelas, estado, exit, log
scripts/run.sh log <sessão>:<nome> [N=40]   # últimas N linhas do log
scripts/run.sh stop <sessão>[:<nome>]       # mata a janela ou a sessão (stop --owner DIR acha pela pasta)
scripts/run.sh reap [--dry-run]             # mata sessões cujo dono (worktree) sumiu
scripts/run.sh install-reaper [--print] [--no-load] | uninstall-reaper
```

Exemplo: `scripts/run.sh start tests --cwd /Users/billiboss/src/x.minha-tarefa --low --slot -- npm test`, depois `scripts/run.sh log x-minha-tarefa:tests 60`.

O dono (`--owner`) é, por padrão, a raiz da worktree git de `--cwd` (ou do pwd); fora de um repo git passe `--owner`. A sessão se chama como a pasta do dono (sem ponto nem dois-pontos), uma janela por `<nome>`, log em `~/.local/state/procs/<sessão>/<nome>.log` (`PROCS_DIR` muda), com um cabeçalho (data, cwd, comando) por início. Códigos: 0 ok, 1 erro, 2 uso.

### Limpeza

- `reap` mata toda sessão do `run.sh` cujo dono não existe mais; sessão sem a marca (`@procs`) nunca é tocada, nem por `stop`.
- Um agente launchd roda `reap` a cada 60 s: `scripts/run.sh install-reaper` (idempotente; copia `run.sh` e `lib.sh` para `~/.local/share/procs/bin/`, porque o caminho do plugin muda a cada versão: rode de novo depois de atualizar o skill). `uninstall-reaper` desfaz.
- **`wt remove` mata a sessão na hora:** o Worktrunk tem o hook `post-remove` (roda em segundo plano, na worktree principal, com `{{ worktree_path }}` apontando a removida; o `pre-remove` bloqueia e roda dentro da worktree). Acrescente ao `~/.config/worktrunk/config.toml`:

  ```toml
  [post-remove]
  procs = "/Users/billiboss/.local/share/procs/bin/run.sh stop --owner '{{ worktree_path }}'"
  ```

  Sem o hook, o reaper cobre em até um minuto.

### Armadilhas dos processos

- **Um processo que se desprende** (`nohup`, `setsid`, um daemon que faz fork) escapa do `stop`: matar a janela manda SIGHUP ao grupo, não a quem saiu dele. Rode o servidor em primeiro plano.
- **Mesmo nome de pasta, outro repo** (`/a/x` e `/b/x`) dá a mesma sessão: o `start` recusa a segunda. Use `--owner` ou outro nome de worktree.
- **`--restart`** faz `respawn-pane -k` na mesma janela (mata o processo velho; matar a única janela derrubaria a sessão). Janela já terminada (`exited`) é reaproveitada sem `--restart`; uma que roda é recusada.
- **O pane tem `tee`**, não o terminal direto: o comando vê um pipe na saída, e programas que só colorem em tty perdem a cor. A vaga (`--slot`) é solta quando o comando acaba, não quando a janela fecha.
- **Vaga presa:** uma vaga de dono morto (pid inexistente) é retomada sozinha pelo próximo `--slot`; não apague `$PROCS_DIR/slots` à mão.
- **Hooks do shell:** chame `run.sh` pelo caminho completo e sem `cd` antes; para esperar, `pane.sh wait <sessão>:<nome> --text 'exit=' --timeout N`, nunca um laço com pausa.

## Estado do agente na aba (agent-state.sh)

A aba do thread acende (` ✓ nome `, branco em negrito sobre bordô) quando o agente Hermes dela termina um turno e o dono não está nela; entrar na aba apaga. Quem dirige são os shell hooks do Hermes (sem polling): `pre_llm_call` → `agent-state.sh working`, `post_llm_call` → `agent-state.sh done`; o `$TMUX_PANE` do TUI identifica a janela. `scripts/agent-state.sh install` liga o hook de limpeza no tmux (e no `~/.tmux.conf`) e imprime o bloco `hooks:`; `uninstall` desfaz. O script não escreve nada em stdout (o Hermes leria como diretiva) e sai 0 sempre; trabalho atrasado (o debounce do sort) vai num subshell com `</dev/null >/dev/null 2>&1 &`, senão o Hermes espera o pipe fechar e o gancho deixa de ser rápido (alvo: < 200 ms). **Ligar um gancho novo:** `hermes -p bili config set hooks.<evento> '[{"command": "<caminho> <arg>"}]'`, acrescente o par `{event, command}` em `~/.hermes/profiles/bili/shell-hooks-allowlist.json` (não há comando de aprovar; sem isso o gancho pede consentimento no primeiro uso) e confira com `hermes -p bili hooks list` (✓ allowed) e `hooks doctor`. As opções da janela são `@agent` (`working`) e `@done` (`1`): o dev-console e o Quadro leem elas antes de raspar o pane. Os comandos também chamam `thread.sh sort <pane>`, que reordena as abas da sessão (lista MRU com a faixa de atenção na frente; ver a skill thread) sem tirar o foco do dono. Pergunta aberta: `on_human_input_request` → `agent-state.sh ask` (` ◆ nome ` sobre bordô, `@ask`) e `on_human_input_resolved` → `agent-state.sh answered`. Subagentes: `subagent_start` → `agent-state.sh sub+` e `subagent_stop` → `agent-state.sh sub-` (a janela é a do `@hsid` = `parent_session_id` do payload) mantêm `@subagents=N`; a aba mostra um glifo cinza (Nerd Font, `AGENT_STATE_ICON` troca, ex. `⚙`) + N antes do nome, e o ✓ só acende quando N chega a 0 depois do fim do turno.

## Atalhos do dono nas abas do Hermes

O TUI do Hermes não deixa remapear teclas; o remapeamento é no tmux, condicionado ao processo do pane (o TUI do Hermes aparece como `python*` em `#{pane_current_command}`), para a tecla seguir normal nas outras abas. Hoje: **Ctrl+K = Alt+K** (reenviar a mensagem "unconfirmed" da fila):

```
bind -n C-k if -F "#{m:python*,#{pane_current_command}}" "send-keys M-k" "send-keys C-k"
```

Aplique no servidor vivo (`command tmux bind …`) e grave a mesma linha no `~/.tmux.conf` (procure antes, para não duplicar), com um comentário dizendo o que ela faz. Confira com `command tmux list-keys -T root | grep C-k` (`list-keys -n` não existe). Só vale dentro do tmux; no app de desktop do Hermes a tecla não muda.

**Fila travada** (`queued (N)` com um `[unconfirmed · Alt+K retry]` no topo, que segura as outras): reenviar só se a mensagem ainda vale. Mensagem velha se apaga: `key <alvo> C-u` (limpa o input), `key <alvo> Up` (entra em "editing 1" na fila), `read` para conferir que o `▸` está na velha, `key <alvo> C-x` (apaga). As seguintes da fila entram no fim do turno atual.

## Evoluir

Mudou um script: rode `scripts/test.sh` (servidor privado, sai 0 só se tudo passa), anote no `CHANGELOG.md` e suba a versão. O teste não cobre um Claude Code de verdade; confira à mão um `send` de `/comando` num TUI, num servidor privado (`TMUX_SOCKET=nome`), nunca na janela de outro agente. Conferido na v0.1.0 com o Claude Code 2.1.318: `/reload-plugins` chega inteiro e executa, um texto de duas linhas aparece digitado, sem Enter, com `--no-enter`, e uma colagem de 41 linhas (3558 caracteres) vira `[Pasted text ...]`, com o Enter enviando e a resposta voltando. `scripts/test.sh` também passa com o bash 3.2 do macOS (`/bin/bash`).
