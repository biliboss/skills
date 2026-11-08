---
name: copywriting
description: Use when writing, rewriting or reviewing text by Gabriel Fonseca that sells an idea (a LinkedIn post, the series "Diário de um Dev em Desconstrução", a LinkedIn article, Marketing Pessoal, a short pitch). Reads the project's premises in Linear first, writes in his voice (acid with ideas, generous with people), opens with a concrete image, measures the draft with scripts/metricas.py, shows it in the Hermes side panel as a LinkedIn-style HTML, makes images only after he approves the text, and only after his OK saves to Linear. Rules live in the biliboss wiki page marketing-pessoal-voz; learnings in references/experiencias.md. Not `linear` (edits Linear itself), `linkedin-publish` (publishes) nor `estudo-html` (studies a tool).
metadata:
  version: 0.2.3
  license: MIT
---

# copywriting — escrever como o Gabriel

A skill geral de escrita do Gabriel: texto que vende uma ideia, não um produto. Hoje ela cobre dois tipos: o **post do LinkedIn** (a série **Diário de um Dev em Desconstrução**) e o **artigo do LinkedIn**. As regras ficam na wiki do repo `~/biliboss`, a fonte da verdade, e esta skill não as repete:

- **`$WIKI_HOME/biliboss/marketing-pessoal-voz.md`**: a voz, as regras numeradas (até a 24) e o formato do Diário. Leia-a inteira antes de escrever.
- **`$WIKI_HOME/biliboss/copywriting-estruturas.md`**: textos reais de Ladeira, Érico Rocha, Paulo Maccedo e Neil Patel desmontados (gancho, virada, prova, fecho).
- **`$WIKI_HOME/biliboss/copywriting-metricas.md`**: as métricas de prosa e a faixa-alvo de cada uma.

Os aprendizados de cada texto, um por linha e datados, ficam em [references/experiencias.md](references/experiencias.md). Quando o Gabriel corrigir o jeito de escrever, corrija a página da voz, acrescente a linha em `experiencias.md` e, se mudar o procedimento, esta skill.

## Passos (todo tipo)

1. **Ler as páginas da wiki** acima (`git -C "$WIKI_HOME" fetch` e `git -C "$WIKI_HOME" show origin/main:biliboss/<página>` se o checkout estiver defasado) e o [references/experiencias.md](references/experiencias.md).
2. **Ler os docs do projeto no Linear** (projeto `75d616a8-32ae-4227-8639-72f69c1ae540`) com `~/src/skills/skills/linear/scripts/lin.sh '{ document(id:"<id>"){title content} }'`: o Norte, a Voz, as Séries, o Aprendizado e o último Diário publicado. Os ids estão na página da voz. Sem ter lido os cinco, não escreva. Se o conteúdo do projeto contradiz o doc 04, vale o doc 04.
3. **Ler o pedido direito.** Quando o Gabriel explica a intenção com uma analogia ("é um palco de teatro"), a analogia é o **porquê**, não conteúdo: ela não vira cena, imagem nem texto. Na dúvida, pergunte numa linha ("o palco é para eu desenhar ou é só o jeito de explicar?").
4. **Alinhar o objetivo** com perguntas de múltipla escolha e oferecer 5 ou 6 aberturas (regra 21 da voz). Os objetivos vão escritos no topo do rascunho, antes do texto (regra 22).
5. **Rascunhar** seguindo a página da voz e o tipo (abaixo).
6. **Medir antes de mostrar.** Rode `scripts/metricas.sh rascunho.md` (desta pasta; `--secao Post` mede só uma seção, `--json` sai em JSON). A métrica é régua, não juiz: o que ficar fora da faixa vai citado nos Bastidores, e quem decide é o Gabriel. As faixas e a origem de cada métrica estão em `$WIKI_HOME/biliboss/copywriting-metricas.md`; as estruturas de referência, em `$WIKI_HOME/biliboss/copywriting-estruturas.md`.
7. **Mostrar no painel lateral** do Hermes (`desktop_preview`) como HTML imitando o LinkedIn, com o aviso de "ainda não salvo no Linear". Nunca escreva no Linear antes do OK.
8. **Imagem só depois do OK do texto** (a ordem fixa, abaixo).
9. **Ajustar** com o feedback dele até o OK, e anotar cada correção em `references/experiencias.md`.
10. **Salvar no Linear** (doc do Diário ou cartão, pela skill `linear`), sem os Bastidores no texto publicável. Nome de cliente só publica com o OK do cliente.
11. **Publicar** pela skill `linkedin-publish` (com a página `linkedin-publicar` da wiki). O passo a passo fica lá e não se repete aqui.

## A ordem fixa: texto primeiro, imagem depois

As imagens só são geradas **depois de o Gabriel aprovar o rascunho do texto no painel lateral**. Antes disso, no máximo uma lista de ideias de imagem, em texto, nos Bastidores. Imagem de um texto que ainda vai mudar é trabalho jogado fora e puxa o texto para caber na imagem.

Quem gera é a skill **`faceless-art`** (personagens faceless de cabeça lisa de manequim, humor editorial brasileiro, fundo claro, sem logos, texto em português, gente real sem caricatura). Siga-a; esta skill só aponta para ela. Mostre a arte no mesmo painel.

## Tipo: post do LinkedIn (o Diário)

O formato está na página da voz: a abertura é uma verdade sem "eu" dita por uma imagem concreta, toda frase carrega informação ou tensão, o detalhe humano só com fatos que ele disse, fato x hipótese x experimento separados, gancho em negrito, parágrafos de 1 a 2 linhas, pergunta final em negrito, assinatura em itálico com o número e a seção "Bastidores (não publicar)". Uma arte por post, depois do OK do texto.

## Tipo: artigo do LinkedIn

A regra 24 da voz. O esqueleto aprovado está em [templates/artigo.html](templates/artigo.html), tirado do artigo "A quarta sócia" (`$WIKI_HOME/biliboss/resources/velumma-diario-02.html`): copie e troque os marcadores `{{…}}`.

- **O objetivo vai escrito no topo do rascunho** e é sempre o mesmo: o leitor se enxergar e pensar "que ideia boa, serve para mim". Os outros dois: o secundário, o cliente (dá vontade de contratar); o oculto, o autor (só por tabela).
- **Nada técnico:** nenhuma ferramenta explicada, nenhum jargão, nada para mostrar o quanto o autor sabe.
- **Uma imagem central simples**, que carrega o artigo inteiro e volta no fecho (como "a quarta sócia").
- **Uma ferramenta prática em texto:** um exercício que o leitor faz hoje, sem ferramenta nenhuma.
- **O fecho é uma pergunta que põe o leitor dentro da ideia** ("qual a primeira coisa que você pediria para ela?"), e o CTA pede para postar o resultado do exercício nos comentários, com a ajuda gratuita.

### As imagens do artigo

- **A capa** tem **1920 × 1080 px (16:9)**, em **PNG ou JPG, nunca GIF**. É a única regra oficial: a [ajuda do LinkedIn sobre imagens e capa no artigo](https://www.linkedin.com/help/linkedin/answer/a516987) diz que o tamanho ideal é 1920 × 1080, que a capa é cortada em 16:9, que aceita JPEG, JPG, PNG e WEBP e que GIF não pode mais ser capa (conferido em 04/11/2026). A capa também tem de ser **entendida pequena**, porque vira a miniatura do feed e do e-mail: uma ideia só, poucos elementos, contraste alto, sem texto miúdo.
- **No corpo vão 3 a 4 imagens**, uma a cada ~250 palavras, cada uma simbolizando um conceito do texto, **nunca enfeite**. Se não dá para dizer numa frase qual conceito a imagem carrega, ela sai.
- **De onde vem o resto:** fora a capa, é opinião de praticante, não regra do LinkedIn. O estudo mais citado é o de Paul Shapiro no OkDork, de 2014 ([How to Post on LinkedIn: 10 Tips from Analyzing 3000 Posts](https://okdork.com/linkedin-publishing-success/)), que achou mais visualizações nos artigos com 8 imagens. É **correlação** (artigos que já iam bem tinham mais imagens; não prova que a imagem causou nada) e **antigo** (o LinkedIn de 2014 não é o de hoje). Os 3 a 4 por artigo são escolha nossa, pelo ritmo de leitura; não cite o estudo como prova.

### O SEO antes de publicar

Não existe skill de SEO própria da casa: usamos as públicas, que quem as publica mantém em dia, e a wiki guarda o que é nosso. Neste passo:

1. **Para escolher o tema e a frase de busca,** carregue a skill pública `seo-keyword-research`. No catálogo do Hermes ela é `skills-sh/thibaultbm/claude-seo-geo/seo-keyword-research`.
2. **Para revisar o rascunho para a busca em IA,** carregue a `seo-aeo-best-practices`, que no catálogo é `skills-sh/sanity-io/agent-toolkit/seo-aeo-best-practices`.
3. **Siga o checklist da casa** em `$WIKI_HOME/biliboss/seo-cheatsheet.md` do biliboss, que tem o mapa `moc-seo.md`. Lá estão os campos do LinkedIn (Gerenciar → Configurações → SEO: o título de SEO e a descrição de SEO) e os exemplos reais.

Se uma das duas skills não estiver instalada no perfil, instale-a antes pelo catálogo. As duas são só texto: não pedem chave nem mandam dados para fora.


## Pitfalls

- Siga o doc 04, não os cartões antigos ("Filosofia da manhã", 3 posts por dia, cotas de funil): são material de pesquisa.
- Não invente número, caso, cliente, citação ou traço de pessoa; o que você escolheu vai marcado em "A conferir".
- Nome de pessoa nunca vai no texto (regra 16); dado pessoal sensível (parentesco, por exemplo) fica fora, salvo pedido dele.
- A analogia com que ele explica o pedido não é briefing de cena: não desenhe o "palco de teatro".
- Imagem antes do OK do texto quebra a ordem fixa, mesmo que "já dê para adiantar".
