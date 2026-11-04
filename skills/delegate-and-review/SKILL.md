---
name: delegate-and-review
description: Passa uma tarefa de código a um subagente desta sessão (Sonnet, pela ferramenta Agent, em segundo plano), que trabalha numa worktree nova do repo certo e abre um PR sem fazer merge; quando ele termina, você revisa o PR e corrige o que a revisão achar, no mesmo ramo. Use quando o dono disser "delega para um subagente", "subagente numa worktree e abre PR", "manda um Sonnet fazer e depois revisa", "delega e revisa", "deixa um agente construir e você corrige", "subagent in a worktree, PR, then review". Não é a `herdr-agentes`, que abre outra sessão numa aba do herdr; este roda dentro desta sessão, e quem revisa e corrige é você.
metadata:
  version: 0.2.4
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
ls apps libs 2>/dev/null; cat package.json | head -30; ls AGENTS.md CLAUDE.md .wiki 2>/dev/null
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
6. **Como fechar:** commits no estilo do repo, com a atribuição do modelo dele, como o bot do app (skill `git-agente`: `bili-git-agente conferir` antes); `git push` e `gh-bot pr create` com o corpo e o rodapé; não fazer merge; deixar a worktree; e o relatório: URL do PR, worktree, ramo, resultado dos testes, decisões tomadas, o que não deu para fazer ou conferir.

- **A atribuição é a do modelo que commita.** No briefing do Sonnet, o `Co-Authored-By` é `Claude Sonnet 5.5 <noreply@anthropic.com>`, com o mesmo `Claude-Session` desta sessão; nos seus commits de correção, o seu modelo.
- **A worktree é dele, criada pelo `command wt`:** o Claude Code nega o `git worktree add` com caminho fora da pasta da sessão, fora do modo bypass, e o `isolation: "worktree"` da ferramenta Agent só isola o repo da sessão. Escreva `command wt`, não `wt`: no shell do Mac, `wt` é uma função que tenta dar `cd` e falha numa sessão de agente.
- Nunca crie a worktree a partir do checkout local com mudanças de outras sessões: sempre de `origin/main`.

## 4. Lance e solte

```
Agent(description="<3 a 5 palavras>", model="sonnet", prompt=<briefing>)
```

- Roda em segundo plano; a notificação chega sozinha. Não leia o arquivo de saída do subagente (é a transcrição inteira e estoura o contexto) e não faça o mesmo trabalho em paralelo.
- Diga ao dono, em poucas linhas: a worktree, o ramo, o que vai no PR e que você revisa quando terminar.
- Você não consegue compactar a própria sessão. Se ele pediu para compactar enquanto espera, diga a ele para digitar `/compact`.

## 5. Revise o PR quando terminar

1. Leia o relatório: URL, testes, decisões, o que ficou de fora.
2. Na worktree dele, rode você mesmo os testes e os tipos. Não confie só no relatório.
3. Revise o diff (`gh pr diff <n>`) com a skill `code-review` (`/code-review medium <n>`), e confira item por item as correções numeradas do briefing: cada uma tem código e teste?
4. Separe o que é achado de verdade (bug, item do briefing faltando, teste que não testa) do que é gosto.

## 6. Corrija os achados

- No mesmo ramo e na mesma worktree, um commit por achado ou um commit de revisão, com a sua atribuição. Rode os testes de novo e `git push`.
- Não faça merge nem deploy: isso é do dono.
- Relate: o PR, os achados e como cada um foi corrigido, o que ficou para ele decidir e o que ainda falta (deploy, teste ao vivo).
- Se a revisão ensinou algo sobre o repo ou o produto, anote no `.wiki` dele, conforme o `AGENTS.md`.
