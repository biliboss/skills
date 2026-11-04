---
name: prime-agent
description: >-
  Run Prime Agent (Prime Intellect) as a data-analysis notebook on the GLM coding plan, never on the Claude subscription. It opens Prime Agent in a pane to the right (herdr or tmux, through the duplo-local-agents skill's scripts/mux.sh; with no multiplexer it prints the command), in its own folder per analysis, writes the BRIEF.md (read-only, numbers plus the exact queries in a file), sends it, follows the session, checks the numbers, and closes every analysis as wiki pages (wiki-smith), promoting the queries that worked to a script, a DuckDB macro or a tile. Every action is a script in scripts/. Use when the user says "usa o prime agent", "abre um prime agent", "analisa com o prime", "prime agent no glm", "caderno de análise", "o que o prime descobriu", "instala o prime agent". Not `pi` (the pi.dev agent with the Claude accounts) nor `duplo-local-agents` (Claude Code or pi sessions); this one drives Prime Agent for analysis.
metadata:
  version: 0.3.1
---

# prime-agent — o caderno de análise no GLM

O Prime Agent é um agente de terminal cuja única ferramenta é um REPL Python que fica vivo a sessão inteira: os dados que ele consulta ficam em variáveis, fora do contexto do modelo, e voltam no resume. Por isso ele serve para **explorar dados** (HyperDX, NATS, logs, a matemática das filas), não para escrever código do dia a dia. O detalhe (como ele funciona, os testes, o que achou) está no `moc-prime-agent` do `.wiki` do repo da casa (`$CASA_REPO_PRINCIPAL`).

`S` abaixo é `scripts/` desta skill; `M` é `mux.sh`, o da skill irmã `duplo-local-agents` (`<skills>/duplo-local-agents/scripts/mux.sh`, a única porta para um pane: `sh <caminho>/mux.sh <verbo> ...`). Nenhum script lê stdin, e nenhum imprime a chave.

## As três regras que nunca mudam

- **Nunca com a assinatura do Claude.** O `/login` "Anthropic (Claude Pro/Max)" dele se identifica como o Claude Code, e o próprio aviso dele fala em conta restrita ou banida. Ele roda no GLM do coding plan da z.ai; Claude nele, só com chave paga da Console.
- **Nunca compartilhar nada com a Prime Intellect.** Na primeira tela, "Share agent traces with Prime Intellect?", a resposta é sempre "Not now". O `S/configurar.sh` desliga traces e telemetria nas configurações, e o `S/rodar.sh` exporta `DO_NOT_TRACK=1`.
- **Sem sandbox.** Ele roda o Python que o modelo escreve com as permissões do usuário: cada análise trabalha na pasta dela (`$PRIME_LAB/<tema>`), e o briefing sempre diz "só leitura".

## Passos

1. **Pronto?** `S/configurar.sh` confere o binário (instala pelo instalador oficial se faltar, depois de baixar e ler o script), põe o padrão no `zai` / `glm-5.3-flash` e desliga traces e telemetria. Rode uma vez por máquina e depois de um `prime-agent update`.
2. **Abrir:** `S/abrir.sh <tema> [modelo]` cria `$PRIME_LAB/<tema>`, abre o Prime Agent num pane à direita do seu, sem tirar o foco, e imprime o pane. Funciona no herdr e no tmux; sem multiplexador, imprime o comando para rodar num terminal à parte (sai com 3). O modelo padrão é o `glm-5.3`, o mais potente para análise; o `glm-5.3-flash` serve para uma tarefa curta.
   - Se a primeira tela perguntar sobre traces, responda "Not now": `M tecla <pane> Down` e depois `M tecla <pane> Enter`, conferindo com `M ler <pane>` entre os dois.
   - **Dois agentes não abrem o mesmo pane:** se outra sessão já abriu um para o tema, use o dela e feche o seu.
3. **O briefing:** copie `templates/BRIEF.md` para `$PRIME_LAB/<tema>/BRIEF.md` e preencha. Ele sempre traz:
   - o objetivo verificável numa frase e a janela de tempo exata;
   - as fontes e como acessar (por exemplo, `mcpc @clickstack tools-call <ferramenta> '<json>'`, com o JSON escapado por `shlex.quote` dentro do Python, senão as aspas simples do SQL somem);
   - as páginas do `.wiki` para ler antes, só leitura;
   - **só leitura** (no HyperDX, nada de `save_`, `delete_` ou `patch_`) e nada fora da pasta do tema; pacote Python só num `.venv` dentro dela (um DuckDB local ajuda a guardar e cruzar o que ele junta);
   - a entrega **em arquivo na pasta do tema**, com os números e a consulta exata de cada um.
   - **Para o HyperDX, use a receita** `references/receita-hyperdx.md`: o briefing, o padrão de funções que funciona, a conferência e o fecho.
4. **Mandar:** uma linha mandando ler o arquivo, pela fila: `M fila <pane> <arquivo-da-mensagem>`.
   - **`fila` é o padrão:** põe a mensagem na fila do agente (Tab no Hermes) para o próximo turno, sem desviar o que ele está fazendo.
   - **`manda` só para corrigir o rumo de um turno** em curso: ele aperta Enter, e o agente larga o que fazia para ler a mensagem.
5. **Acompanhar:** nenhum multiplexador sabe quando o Prime Agent para (o herdr o mostra como `unknown`), então siga pela sessão e pela tela.
   - `S/sessao.sh <tema>` mostra a sessão da pasta: o id, as células do REPL com o tamanho do resultado, os erros e os tokens por turno.
   - `M ler <pane> 80` mostra a tela; com Ctrl+O no pane (`M tecla <pane> C-o`), ela mostra também o raciocínio.
   - A entrega pronta é o arquivo na pasta do tema.
6. **Conferir:** antes de qualquer número ir para o wiki ou para um cartão, rode de novo as 2 ou 3 consultas principais (`mcpc` direto) e compare. Aponte as contas erradas a ele no mesmo pane, para ele corrigir o arquivo.
7. **Fechar no wiki (sempre):** toda análise do Prime Agent termina como informação no `.wiki` do repo da casa, pela skill `wiki-smith`:
   - uma página `prime-agent-<tema>.md` com a janela, os achados numa tabela (o número e de onde veio), o que foi conferido e o que não foi, e o que fazer;
   - a página ligada no `moc-prime-agent`, e uma nota no diário;
   - o que vale além da análise vai para a página do assunto (por exemplo, a regra nova de um painel).
8. **Promover o que deu certo:** a consulta que vai se repetir sai do REPL e vira um script do repo, uma macro do DuckDB (skill `database-skill-creator`) ou um tile do HyperDX. O estado do REPL (`kernel-state.dill`) não é fonte de verdade: quebra num upgrade e nenhum outro agente o lê.
9. **Agir sobre os achados:** trabalho da VPS vai para o Bili num cartão (skills `linear` e `bili`), seguindo o AGENTS.md do Linear: um cartão de resultado com os achados como checklist, não um cartão por achado.

## Exemplo: sugestões a partir do HyperDX

1. `S/abrir.sh hyperdx glm-5.3-flash` abre o pane em `$PRIME_LAB/hyperdx`.
2. O `BRIEF.md` da pasta segue a `references/receita-hyperdx.md`: 3 sugestões, 48 h, só leitura, com o tile e o SQL de cada número.
3. Em ~6 min ele entrega o `sugestoes.md`; `S/sessao.sh hyperdx` mostra como chegou lá.
4. Você confere 2 ou 3 números com o `mcpc` e as contas que ele fez por cima.
5. O fecho é a página `prime-agent-hyperdx.md` no wiki e um cartão de resultado com os achados como checklist, para o Bili.

## O que pega

- **Retomar:** `S/rodar.sh --resume <id>` de dentro da pasta do tema, com o mesmo modelo; o id vem do `S/sessao.sh`.
- **`prime-agent model list` só mostra o `zai` com a chave no ambiente:** rode-o pelo `S/rodar.sh model list`.
- **Ele imprime arquivos inteiros quando lê contexto:** peça no briefing que leia só as seções que importam, para não gastar contexto à toa.
- **Só `M` fala com o multiplexador:** os passos não chamam `herdr` nem `tmux` direto, para a skill rodar em qualquer um. Outro multiplexador entra como um ramo novo no `mux.sh`, com os mesmos verbos. Cada pane tem um id de dois dígitos que diz o dono: `TNN` no tmux (nas opções `@tnn`/`@nome` do pane, porque o Claude Code sobrescreve o título) e `HNN` no herdr (no rótulo, `HNN - nome`); a mesma sessão conduz os dois. `M panes` lista todos, e `nomear <pane> <nome> [ID]` dá o próximo id livre.
- **No REPL do Prime Agent, use a skill Python `mux`** (`python/mux/`, ligada em `~/.agents/skills/mux`): `mux.panes()`, `mux.ler`, `mux.tecla`, `mux.fila`, `mux.manda`, `mux.nomear`, `mux.abrir`, que só chamam o `mux.sh` da `duplo-local-agents`.
- **No tmux, ligue `set -g extended-keys on`** no `~/.tmux.conf`: sem isso o Prime Agent avisa que o Enter com modificador (nova linha na caixa) pode falhar.
- **No herdr, registre o pane** na foto do `.wiki/herdr-sessoes.md`, como qualquer sessão de agente.
