---
name: copywriting
description: Use when writing, rewriting or reviewing text by Gabriel Fonseca that sells an idea (a LinkedIn post, the series "Diário de um Dev em Desconstrução", Marketing Pessoal, a short pitch). Reads the project's premises in Linear first, writes in his voice (acid with ideas, generous with people), opens with a concrete image, drafts in the Hermes side panel as a LinkedIn-style HTML, gets the art made by a subagent, and only after his OK saves to Linear. Rules live in the biliboss wiki page marketing-pessoal-voz. Not `linear` (edits Linear itself) nor `estudo-html` (studies a tool).
metadata:
  version: 0.1.0
  license: MIT
---

# copywriting — escrever como o Gabriel

A skill geral de escrita do Gabriel: texto que vende uma ideia, não um produto. O post do LinkedIn (a série **Diário de um Dev em Desconstrução**) é a primeira aplicação. As regras ficam numa página só, a fonte da verdade: **`.wiki/marketing-pessoal-voz.md`** no repo `~/biliboss` (leia-a inteira antes de escrever; esta skill não a repete). Quando o Gabriel corrigir o jeito de escrever, corrija a página e, se mudar o procedimento, esta skill.

## Passos

1. **Ler a página da wiki** `~/biliboss/.wiki/marketing-pessoal-voz.md` (`git -C ~/biliboss fetch` e `git show origin/main:.wiki/marketing-pessoal-voz.md` se o checkout estiver defasado).
2. **Ler os docs do projeto no Linear** (projeto `75d616a8-32ae-4227-8639-72f69c1ae540`) com `~/src/skills/skills/linear/scripts/lin.sh '{ document(id:"<id>"){title content} }'`: o Norte, a Voz, as Séries, o Aprendizado e o último Diário publicado. Os ids estão na página. Sem ter lido os cinco, não escreva. Se o conteúdo do projeto contradiz o doc 04, vale o doc 04.
3. **Rascunhar** seguindo a página: a abertura é uma imagem concreta (com duas alternativas para o Gabriel), toda frase carrega informação ou tensão, o detalhe humano só com fatos que ele disse, fato x hipótese x experimento separados, formato do Diário (gancho em negrito, parágrafos de 1 a 2 linhas, pergunta final em negrito, assinatura em itálico com o número) e a seção "Bastidores (não publicar)".
4. **Mostrar no painel lateral** do Hermes (`desktop_preview`) como HTML imitando o LinkedIn, com o aviso de "ainda não salvo no Linear". Nunca escreva no Linear antes do OK.
5. **Arte** por um subagente que usa o Codex CLI (geração de imagem da OpenAI): personagens faceless de cabeça lisa de manequim, humor editorial brasileiro, fundo claro, sem logos, texto em português, gente real sem caricatura. Mostre a arte no mesmo painel.
6. **Ajustar** com o feedback dele até o OK.
7. **Salvar no Linear** (doc do Diário ou cartão, pela skill `linear`), sem os Bastidores no texto publicável. Nome de cliente só publica com o OK do cliente.

## Pitfalls

- Siga o doc 04, não os cartões antigos ("Filosofia da manhã", 3 posts por dia, cotas de funil): são material de pesquisa.
- Não invente número, caso, cliente ou traço de pessoa; o que você escolheu vai marcado em "A conferir".
- Dado pessoal sensível (parentesco, por exemplo) fica fora, salvo pedido dele.
