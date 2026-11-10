# Mapa do código vira modo da skill `wiki` e o PR #143 passa a usá-lo

## Contexto

O Luiz abriu o PR viacorretor/the-viacorretor#143 por conta própria, numa sessão do Claude Code na web, sem issue. O PR traz três coisas:

- `docs/CODEBASE_MAP.md`;
- a skill `cartografo`, no próprio repo, adaptada do Cartographer (kingbootoshi, MIT);
- uma seção no `CLAUDE.md` que manda ler o mapa antes de explorar.

O conteúdo tem valor. A wiki do Via tem 18 páginas por tema, mas nenhuma é a planta do código. A primeira armadilha do mapa já achou uma frase errada no `CLAUDE.md`. A revisão do agente (bili-clone) não achou bug nem regra quebrada.

O problema é o lugar e a validade:

- O mapa nasce fora da wiki, o que cria uma segunda memória.
- A skill nasce dentro do repo, longe do plugin `biliboss/skills`.
- O mapa só se atualiza se alguém lembrar.

Decisão do dono: o método entra na nossa skill `wiki`, e o #143 é refeito com o Luiz para usá-la.

## Resultado

1. A skill `wiki` tem o modo **mapa**:
   - cria a página da planta do código de um projeto;
   - atualiza só os módulos que mudaram;
   - acusa quando a página ficou velha.
2. O #143 entra trazendo só o mapa do Via como página da wiki, com o `CLAUDE.md` apontando uma vez para a wiki. A skill `cartografo` sai do PR.
3. O Luiz aparece como coautor no PR e nos créditos da skill.

## Parte 1: modo mapa na skill `wiki` (biliboss/skills)

| Peça | O que faz |
|---|---|
| `scripts/map.py` | Porta do `mapear.py`, só com a biblioteca padrão. Lista os arquivos com `git ls-files`, estima os tokens (bytes/4) por pasta e sai em texto ou JSON. Com `--check <página>`, sai com erro quando a estrutura diverge ou quando um módulo mudou depois do `last_mapped`, e lista os módulos velhos. |
| `templates/code-map.md` | A página com frontmatter da wiki (`created`, `updated`) mais `last_mapped`, `total_arquivos` e `total_tokens`. Seções: visão geral, estrutura, módulos, fluxos, convenções, armadilhas, onde mexer. |
| `SKILL.md`, seção "Code map" | **Criar:** medir, dividir em grupos de até ~120k tokens, um subagente Explore por grupo, todos numa mensagem, e escrever. **Atualizar:** `git log --since=last_mapped`, remapear só os módulos mudados e reescrever só as seções deles. **Regra:** só nomes de variável, nunca valores nem dado pessoal. |
| `lint.py` | Chama o `map.py --check` quando a wiki tem página de mapa, e o aviso de mapa velho entra no lint. |
| `ATTRIBUTION.md` | Credita o Cartographer (MIT) e o Luiz pela adaptação. |
| `CHANGELOG.md` | Nova versão. |

**Onde entra:** a skill `wiki` ainda está no branch local `devin/20261108-212522-p2-central`, sem publicar e esperando o PR #201. Ou o modo mapa entra nesse branch, ou espera a publicação. O repo é do Bili Skills, então o pedido vai para ele.

## Parte 2: refazer o #143 com o Luiz

- `docs/CODEBASE_MAP.md` vira `.wiki/mapa-do-codigo.md` no formato do template, com o `last_mapped` renovado pelo modo atualizar, porque o #147, o #145 e o #142 entraram depois.
- `.wiki/index.md` ganha o link para o mapa.
- `.claude/skills/cartografo/` sai.
- No `CLAUDE.md`, a seção nova vira duas linhas:
  - a wiki em `.wiki/index.md` é a memória do projeto;
  - a planta do código está em `.wiki/mapa-do-codigo.md`.
  A linha repetida no "padrão de design" sai.
- O `CLAUDE.md` corrige "Push em `main` roda a suíte", que deixou de valer em 07/11 (armadilha 1). Também tira "assinatura (desligada)".
- Quando a wiki do Via for para o `biliboss/wiki` (o Via é o último da migração), a página vai junto.

**Co-criação:** comentar no #143 com este plano e combinar com o Luiz quem faz cada parte. Depois disso, o bili-clone empurra commits no branch dele, ou ele mesmo faz.

## Parte 3: validade automática no Via (depois)

Um check do `via-doctor` acusa quando um módulo do mapa mudou depois do `last_mapped`, porque o CI não alcança o script do plugin. Fica para um PR próprio, depois de a Parte 1 provar o formato.

## Ordem

1. Parte 1 no plugin (Bili Skills), com prova.
2. Parte 2 no #143, com o Luiz; revisão do agente; revisão do dono; squash.
3. Parte 3, se o dono quiser.

## Prova

- `map.py` no checkout do Via dá os mesmos totais do `mapear.py` do Luiz.
- `map.py --check` acusa o mapa de 09/11 como velho e lista os módulos do #147 e do #142. Depois do modo atualizar, ele passa.
- `lint.py -w .wiki` passa no Via com a página nova.
- Uma sessão nova no Via acha o mapa pelo `CLAUDE.md` sem buscar.

## Decisões do dono (10/11)

1. A Parte 1 entra no branch `devin/20261108-212522-p2-central`, junto com a skill `wiki` 0.2.0. Esse branch só existe local, com 5 commits à frente da `main`. Para o Build vê-lo, ele precisa ir para o `origin` como base, sem PR para a main e sem merge.
2. O bili-clone refaz o #143 e o dono revisa. Não precisa do OK do Luiz: o bili-clone é sempre quem faz os PRs. O Luiz é avisado num comentário e fica com o crédito.
3. A Parte 3 entra agora, no mesmo #143. O check do `via-doctor` compara o `last_mapped` da página com o `git log` dos módulos que ela lista. O CI passa a cobrar o mapa desde o início.

## Execução (padrão: issue, PR com o plano, Build)

1. **biliboss/skills**
   - Empurro o `p2-central` para o `origin`.
   - Abro a issue da Parte 1 e o PR com o plano (bili-clone) contra esse branch.
   - Rodo `bili-agents run build -i biliboss/skills#<n>`.
   - Reviso, o dono revisa, e a mudança entra no `p2-central`.
2. **viacorretor/the-viacorretor**
   - Abro a issue das Partes 2 e 3, apontando o #143 e a skill nova.
   - Rodo `bili-agents run build -i viacorretor/the-viacorretor#<n>` no branch do #143.
   - Rodo a revisão do agente, depois a revisão do dono e o squash.
