---
name: delegate-and-review
description: Passa uma tarefa de código a um subagente desta sessão (Sonnet, pela ferramenta Agent, em segundo plano), que trabalha numa worktree nova do repo certo e abre um PR sem fazer merge; quando ele termina, você revisa o PR e corrige o que a revisão achar, no mesmo ramo. Use quando o dono disser "delega para um subagente", "subagente numa worktree e abre PR", "manda um Sonnet fazer e depois revisa", "delega e revisa", "deixa um agente construir e você corrige", "subagent in a worktree, PR, then review". Não é a `duplo-local-agents`, que abre outra sessão numa aba do herdr; este roda dentro desta sessão, e quem revisa e corrige é você.
metadata:
  version: 0.3.3
---

# delegate-and-review — delegar a um subagente, revisar o PR e corrigir

O subagente só sabe o que está no briefing, e você só vê o relatório dele. Por isso o trabalho que fica com você é o briefing (antes) e a revisão (depois). O meio é dele.

## 1. Tire a tarefa da conversa

"Delega isso" quase nunca diz o quê. A tarefa já está na conversa: comece por ela, não pelo dono.

- **Onde procurar, nesta ordem:** o próximo passo que você ofereceu ou recomendou por último (e o que ele respondeu), o "PRÓXIMO" de um repasse de outra sessão, a página de desenho ou a Task List citada, e os achados da sua última revisão que ainda não viraram código.
- **O repo** sai do mesmo lugar: o caminho do código discutido, não o da sessão (ex.: a sessão roda num repo de notas e o código está noutro, de um projeto à parte).
- **Leve ao briefing tudo o que a conversa já estabeleceu:** fatos conferidos, decisões do dono, correções, limites ("não fazer deploy", "não mexer em X"). O subagente não vê a conversa.
- **Sem 100% de clareza, pergunte antes de lançar:** o quê, em qual repo, o que entra no PR e o que fica fora. Se qualquer um tiver mais de uma leitura, pergunte (errar a tarefa custa um PR inteiro). Pergunte uma vez, pela `AskUserQuestion`, a ferramenta padrão de pergunta, e não pelo formulário da skill `interview`: uma pergunta só, com as leituras como opções, cada uma dizendo o repo e o que entra no PR, e a que você recomenda primeiro, com "(Recomendado)".

## 2. Olhe o repo antes de escrever o briefing

```sh
cd <repo> && git fetch -q && git status -sb | head -3 && git log --oneline -3
ls apps libs 2>/dev/null; cat package.json | head -30; ls AGENTS.md CLAUDE.md $WIKI_HOME/<projeto> 2>/dev/null
```

- Anote os comandos de teste e de tipos (`bun test`, `bun run typecheck`, `npm test`…) e quantos testes passam hoje: o subagente precisa de uma linha de base.
- Confira à mão os fatos que o briefing vai afirmar (um contrato de API, um caminho, um status). Marque o que não foi conferido como "a conferir": o subagente que recebe uma hipótese tende a devolvê-la confirmada.

## 3. Escreva o briefing

Ele é o único contexto do subagente. Seções, nesta ordem:

1. **Objetivo**, em uma frase, e o que está fora (sem merge, sem deploy, sem mexer no que está no ar).
2. **Setup:** a worktree nova, criada por ele com o worktrunk, e o que ler primeiro (o `AGENTS.md` do repo, os arquivos certos, a página de desenho). Ele trabalha só no caminho que o `wt` mostrar, com `git -C <worktree> …`.
   ```sh
   git -C <repo> fetch origin main && git -C <repo> merge --ff-only origin/main
   command wt -C <repo> switch --create run/<tema> --base main   # cria <repo>.run-<tema>, ao lado do repo
   ```
3. **O que já existe**, em poucas linhas.
4. **Os fatos conferidos** (o contrato, os erros, os limites) e as **correções ao desenho**, numeradas, cada uma testável.
5. **Testes** que ele tem de escrever, com os casos difíceis nomeados.
6. **Como fechar:** commits no estilo do repo, com a atribuição do modelo dele; `git push` e `gh pr create` com o corpo e o rodapé; não fazer merge; deixar a worktree; e o relatório: URL do PR, worktree, ramo, resultado dos testes, decisões tomadas, o que não deu para fazer ou conferir.

- **A atribuição é a do modelo que commita.** No briefing do Sonnet, o `Co-Authored-By` é `Claude Sonnet 5.5 <noreply@anthropic.com>`, com o mesmo `Claude-Session` desta sessão; nos seus commits de correção, o seu modelo.
- **A worktree é dele, criada pelo `command wt`:** o Claude Code nega o `git worktree add` com caminho fora da pasta da sessão, fora do modo bypass, e o `isolation: "worktree"` da ferramenta Agent só isola o repo da sessão. Escreva `command wt`, não `wt`: no shell do Mac, `wt` é uma função que tenta dar `cd` e falha numa sessão de agente.
- Nunca crie a worktree a partir do checkout local com mudanças de outras sessões: sempre de `origin/main`.
- Depois do merge, quem juntou roda `wt remove <ramo>`: só apaga o que já está no main (`⊂`); nunca `-D`.
- **Código que vai de um repo privado para um público** sai do `origin` (`git archive <remoto>/main <pasta> | tar -x --strip-components=N`), sem dados, legado nem cópia de produto, e passa por um `grep` de caminho pessoal (`/Users/`), nome de cliente, repo privado e id de produto, também nos testes e nos exemplos da doc. Troque os ids por genéricos (`loja/`, `acme/`) e rode os testes: a troca muda a ordem alfabética que um teste pode conferir.

## 4. Lance e solte

```
Agent(description="<3 a 5 palavras>", model="sonnet", prompt=<briefing>)
```

- Roda em segundo plano; a notificação chega sozinha. Não leia o arquivo de saída do subagente (é a transcrição inteira e estoura o contexto) e não faça o mesmo trabalho em paralelo.
- Diga ao dono, em poucas linhas: a worktree, o ramo, o que vai no PR e que você revisa quando terminar.
- Você não consegue compactar a própria sessão. Se ele pediu para compactar enquanto espera, diga a ele para digitar `/compact`.

## 4b. Vários em paralelo (o limite é a máquina)

- **Faça a triagem no começo do turno:** o que leva mais de 2 min vai a subagentes assíncronos; você só tria e confere, e a fila esvazia num turno, não em vários. Ficar um turno inteiro fazendo à mão o que um subagente faz é o erro que o dono mais aponta. Trabalho longo nunca vira thread (skill `thread`) por iniciativa do agente: thread só abre quando o dono pede uma, com essas palavras, porque cada thread é uma sessão do tmux que ele precisa ver e fechar.
- **O limite é o recurso da máquina, não um número fixo.** Antes de soltar, confira memória livre (free + inactive > 1,5 GB) e load de 1 min < núcleos; se não cabe, espere ou mande ao agente remoto. No Hermes, o teto é `delegation.max_concurrent_children` (o `max_async_children` é ignorado); orçamento por filho com `delegation.max_iterations` (~60) e `delegation.child_timeout_seconds`. O agente não edita o `config.yaml` direto: use `hermes -p <perfil> config set|unset <chave>`.
- **Escopo de ~10 min por subagente.** Tarefa maior vira vários em paralelo, divididos por dono de arquivo (ex.: fonte+layout num, widgets noutro, o watcher noutro). Um subagente de 25+ min é o sinal de escopo grande demais.
- **Regras de velocidade em todo briefing:** sem `sleep` (espere por evento ou não espere); não reiniciar processo à mão nem abrir janela no tmux do dono (TUI e testes rodam num watcher com log, e o subagente lê o log); código por patch/write_file, nunca heredoc; script em arquivo em vez de `python3 -c` (o `-c` cai na aprovação e para o fluxo); editar e testar na mesma chamada; renomear em massa num script só.
- **Serviço de longa duração não sobe como processo de fundo do subagente:** ele morre quando o subagente termina. Suba-o num pane fixo (ex.: a aba de serviços do herdr, `herdr pane split` + `herdr pane run`) com log em arquivo.
- **Nem roda de dentro do scratch:** a pasta de rascunho do Hermes apaga o que fica 24 h parado, e um servidor (um Storybook, um dev server) que mora ali perde o `node_modules` e passa a responder erro (`ENOENT … iframe.html`) sem cair. Clone que serve alguma coisa por mais de um dia mora em `~/src/<repo>`, com log em `~/.local/state/<serviço>.log`.
- **Cada subagente é dono dos seus arquivos.** Diga no briefing quais arquivos são dele e quais são de outro subagente, e que ele commita só os dele, pelo caminho. Dois subagentes no mesmo arquivo perdem trabalho.
- **Várias features que tocam o mesmo núcleo (um loader, um schema) vão em duas fases:** na primeira, um subagente mexe no núcleo e os outros escrevem cada um um módulo puro num arquivo novo, com testes próprios e a API exata no briefing; na segunda, um integrador liga os módulos ao núcleo, e outro, em paralelo, só faz docs e scripts. Você commita entre as fases. Sem isso, três subagentes disputam o mesmo arquivo. Com isso, as fases rodam em ~4 min cada, contra a fila serial.
- **Correção chega por steer, com os números exatos** ("raiz 50/50, barra com 2 linhas"), não refazendo à mão. Se você mexe ao mesmo tempo no que ele está aplicando ao vivo (um layout, um processo), os dois desfazem um ao outro. Se ele já terminou, o steer não chega (o subagente não existe mais): despache outro com o briefing completo.
- **Confira cada entrega no remoto** (`git fetch` e `git log origin/<ramo>`) antes de contar ao dono, e procure nos relatórios o que ficou entre dois donos (um arquivo que nenhum dos dois atualizou).
- **Quando um subagente publica e outro lê a mesma coisa (um evento, um KV, um arquivo de config), fixe o contrato nos dois briefings antes de lançar:** o nome exato (subject, chave, rótulo) e os campos. Sem isso, cada um inventa o seu nome, e quem lê não acha o que o outro publica. Se o contrato mudar no meio, mande o mesmo steer aos dois.
- **O mesmo vale para um protocolo descrito em paralelo** (a skill que o define, a página da wiki do projeto (skill `wiki`) que o explica, a primeira ferramenta que o segue): escreva o protocolo inteiro, com a escala de status e os códigos de saída, em todos os briefings. Quem recebe um "0/1/2" sem o significado escolhe o seu, e a casa fica com duas escalas. Ao conferir, compare as entregas entre si, não só cada uma com o briefing, e corrija a que divergir para a da skill.
- **"X não existe" num relatório pode estar velho:** um irmão pode ter acabado de criar. Confira (um `ls`, um `grep` no ramo remoto) antes de repassar a falta ao dono ou de despachar quem a faça.
- **Arquivo compartilhado tem um dono só** (um justfile, um config). O subagente pede a mudança ao dono, com a interface exata (script, argumentos, linha de doc), e não edita. Se dois escrevem no mesmo arquivo ao mesmo tempo, sai uma receita duplicada e a CLI quebra.
- **Subagente fazendo estrago ao vivo leva `stop`, não steer.** O steer só chega no próximo limite de ferramenta, e até lá ele segue publicando ou mexendo. Pare, limpe você mesmo e despache outro com o briefing completo, com a regra que faltou.
- **Estado ao vivo no briefing vai com ids reais, conferidos agora,** e com o jeito de achá-los de novo pelo papel (rótulo, título do terminal, config), não só pelo id: ids de pane e de rótulo mudam no meio da tarefa, e um id fixo no briefing faz o subagente mexer no pane errado. A `delegate_task` recusa marcador `<...>` no objetivo: substitua antes.
- **Todo objetivo delegado começa pelo projeto e o cartão** ("viacorretor DVM-235 · Apply the milestone rule…"; sem cartão, só o projeto: "mesa · …"), e leva `item=<tema>` no objetivo ou no contexto, com o tema da aba em foco. O prefixo deixa o painel de subagentes legível sem abrir nada. O hermes-watch casa os eventos do subagente (`subagent.*`, `tool.*`) com o item por essa marca. Sem ela, o item sai vazio quando o watcher demora a ver o subagente, e a Activity do focus perde o trabalho dele.
- **No briefing, peça comandos simples e separados,** sem heredoc em pipe para um interpretador e sem `rm -rf`, e diga: "se um comando pedir aprovação, pule, anote e siga". Um script longo com várias partes cai na aprovação de comando, e o subagente para à espera de um clique que ninguém dá, sem entregar nada.
- **Rascunho para o dono aprovar é entrega própria:** quando o pedido diz "mostre antes de aplicar", o briefing diz "não mude nada em <sistema>" e pede o arquivo com a tabela. A aplicação vai num segundo despacho, depois do OK.
- **Antes de um steer, veja se o subagente ainda vive** (`action=list`). Um steer para quem já terminou volta como `missed_steer`, e a correção se perde em silêncio.
- **Pedido que sai da sua fila no meio do trabalho** ("quem roda é outro"): pare na hora, feche o que você abriu (processos em segundo plano, apps, servidores) e restaure o que sobrescreveu para rodar (um bundle de build, um config). Guarde a cópia original antes de sobrescrever, para que essa volta seja um `cp`.
- **Despacho refeito depois de um travamento** aponta para o que o anterior já leu (o scratch dele) e dá o estado real conferido agora, para o novo não repetir as leituras nem trabalhar sobre um estado velho.
- **Acompanhar o trabalho de um agente remoto** (o Bili da VPS num cartão): um subagente por cartão, que só lê, sem escrever código. Ele lê o estado, as atividades da sessão de agente, os comentários e o PR. Se o cartão está parado há mais de 15 min, ele posta UM comentário com o próximo passo concreto, por quem abre a sessão do agente. Para esperar, usa um evento (`nats sub … --count 1` com `timeout`), nunca `sleep`. Devolve duas linhas: o estado e o próximo passo, e a linha do dono só nos quatro casos, com o comando exato. Diga no briefing que um bloqueio técnico (ruleset que exige code owner, permissão de app) não é linha do dono: o subagente nomeia a trava e propõe tirá-la, senão ele devolve "👤 aprovar o PR" e o cartão para.
- **Benchmark ou medição:** despache o texto exato que o dono deu, sem contexto extra, e não ajude nem revise. Qualquer acréscimo seu contamina a comparação.
- **Mudança grande de desenho no meio da tarefa:** é melhor parar e despachar de novo do que empilhar steers. Vários steers seguidos deixam a entrega meio de um jeito, meio de outro.
- **Mudança de código vai a subagente, com o modelo do tamanho do passo, até no dev-console** (o mecânico ao Haiku, o código ao Sonnet, a UI ao Opus); o agente principal só divide, confere e responde. A exceção é o dono dizer "edita aqui" / "right here": aí o agente principal edita na sessão, mostra na tela dele e junta na hora, com as mesmas portas (a suíte da skill antes do PR). Dois remendos à mão que não resolvem são o sinal para despachar.
- **Quando o dono simplifica no meio ("talvez já resolva abrindo no browser"), mande ao subagente vivo um steer com a regra final inteira,** dizendo que ela substitui as anteriores e o que sai: steers que só somam deixam a entrega com as duas versões.
- **Trabalho de UI vai ao Opus com esforço máximo, sempre** (telas, widgets, layout, a aparência do console, views Swift, CSS): é trabalho focado que pede gosto, e o Sonnet entrega a UI que "compila" mas quebra no uso (atalho que não dispara, layout cortado). No Hermes, com o plugin advanced-delegation, `delegation.backend: model_map` tem a rota `ui-opus-max` (Opus, `reasoning_effort: max`) ao lado da `sonnet` padrão; o backend novo só vale depois de `/new`. No Claude Code, `model: "opus"` na ferramenta Agent.
- **No Hermes** a ferramenta é a `delegate_task`, em segundo plano: `action=list` para ver quem vive, `steer` para corrigir e `stop` para parar. O resultado só chega depois que o seu turno termina, então feche o turno com uma linha de status em vez de esperar.
- **Numa sessão one-shot (sem TTY, `-z`, thread), o teto é `delegation.oneshot_max_children` (2) por sessão inteira, e um `delegate_task` com mais tarefas que o teto é recusado todo, sem rodar nenhuma.** Junte as entregas em no máximo 2 tarefas (cada uma dona de um grupo de arquivos), e gaste os subagentes no trabalho mais longo da sessão: depois deles, o resto é seu.
- **Subagente que caiu (limite de conta, timeout) pode ter escrito os arquivos antes de cair:** liste o disco (`ls` nos caminhos do briefing) antes de refazer, e trate o que achar como não conferido até olhar o print.

## 4c. Teste de evento nunca no barramento real

- **Todo teste que publica evento sobe um NATS próprio** (`nats-server -js -p <porta livre> -sd $(mktemp -d)`, com o `NATS_URL` apontando para ele, desligado no fim) ou usa os subjects `test.>`, fora do stream real. As views, os monitores e as avaliações leem o stream real, e um evento falso entra nos números e na tela do dono.
- **Diga isso no briefing de todo subagente que mexe em evento,** com o subject proibido escrito por extenso. Sem isso, o "teste de ponta a ponta" que ele faz é publicar no stream de verdade.
- **Não sondar um serviço com `--help` contra o real:** num script de laço (um watcher, um despachante), `--help` pode não existir e o laço sobe de verdade contra o barramento. Leia o código para saber a interface, ou rode com o `NATS_URL` do servidor de teste.
- **O publicador redige os segredos em todo campo que publica,** não só no log ou na saída. O teste usa uma chave falsa e confere que ela nunca sai crua.
- **Se um evento falso já entrou:** pare o subagente e o processo dele, apague as mensagens por sequência (`js.delete_msg(stream, seq)`, achadas por subject e trace) e procure o id falso nos KVs.

## 5. Revise o PR quando terminar

**Revisão por agente independente**, quando o dono quer o merge sem esperar um humano: despache um subagente **novo**, sem o contexto de quem escreveu. Ele recebe o diff, os requisitos originais e os focos que importam (o modo seguro, segredo ou dado pessoal no repo e no log, nada da casa num repo público, testes rodados por ele, README e skill batendo com o código). Ele só relata, sem mudar nada: achados com severidade, `arquivo:linha` e a correção, e no fim MERGE ou NO-MERGE. O revisor que escreveu o código acha menos.

1. Leia o relatório: URL, testes, decisões, o que ficou de fora.
2. Na worktree dele, rode você mesmo os testes e os tipos. Não confie só no relatório.
2b. **Rode uma fumaça de ponta a ponta pelo caminho real** (o servidor numa porta livre, a página num navegador headless e um cliente em script que chama as ferramentas como o usuário chamaria), com os exemplos que a própria doc do PR promete. A suíte verde do subagente testa o que ele mesmo imaginou: exemplo da doc que o validador recusa e erro que esconde os outros só aparecem no uso. Cada bug achado volta com teste de regressão.
   - **Pare o seu servidor de teste pelo PID ou pela porta** (`lsof -ti :<porta> | xargs kill`), nunca por `pkill -f <padrão>`: o padrão casa também o servidor de verdade do dono.
   - O script da fumaça fica no scratch, fora do repo; para ele achar as dependências, faça um link `node_modules` para o do projeto.
3. Revise o diff (`gh pr diff <n>`) com a skill `code-review` (`/code-review medium <n>`), e confira item por item as correções numeradas do briefing: cada uma tem código e teste?
4. Separe o que é achado de verdade (bug, item do briefing faltando, teste que não testa) do que é gosto.

## 6. Corrija os achados

- No mesmo ramo e na mesma worktree, um commit por achado ou um commit de revisão, com a sua atribuição. Rode os testes de novo e `git push`.
- **O script que junta para no teste vermelho:** `out=$(<teste> 2>&1 | tail -1); [ "$out" = "OK" ] || exit 1` antes do push. Um `| tail` engole o código de saída, e o PR entra com a suíte quebrada.
- **O `gh-app` recusa merge de propósito** ("o merge é de uma pessoa"): o subagente abre o PR e para, e o relato dá ao dono o link do PR para o merge. Não tente outro token para contornar; se o dono quiser merge por agente, a trava a tirar é essa.
- **Merge só com a permissão escrita do dono no pedido.** Com ela: corrija os blockers e as decisões que a revisão levantou (decida pela recomendação e escreva a decisão no README ou no PR), rode os testes uma vez, faça o merge squash pelo app (`gh pr merge <n> --squash --delete-branch`, com o token do app) e comente no PR "revisado por agente: …" com o resumo. Sem a permissão, ou com um achado grave que não dá para corrigir agora, não faça o merge e diga o quê. Deploy continua com o dono.
- **Dois PRs abertos que sobem a versão do mesmo plugin** (`plugin.json` e o CHANGELOG da raiz): junte primeiro o de versão menor; no outro, faça `git merge origin/main` no ramo (não rebase: o `gh-app` recusa push com force, até `--force-with-lease`), resolva o CHANGELOG pondo o bloco novo acima do já juntado e o `plugin.json` com a descrição do main e a versão do ramo, rode os testes e só então o merge.
- Relate: o PR, os achados e como cada um foi corrigido, o que ficou para ele decidir e o que ainda falta (deploy, teste ao vivo).
- Se a revisão ensinou algo sobre o repo ou o produto, anote no `$WIKI_HOME/<projeto>` dele, conforme o `AGENTS.md`.
