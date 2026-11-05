---
name: estudo-html
description: Estudar uma ferramenta, biblioteca ou ideia e entregar o estudo como uma página HTML local (não um Artifact do Claude), aberta numa janela nova do Chrome e guardada no `.wiki/resources/` do repo da casa (`$CASA_REPO_PRINCIPAL`), com veredito, comparação em matriz e onde aquilo entra no nosso sistema. Use quando o dono disser "study X", "estuda o que é isso", "cria um HTML (not Claude Artifact)", "abre numa janela nova", "compara com o Hermes / com o que usamos", "põe em matrizes de comparação", "matriz ASCII contra dez coisas", "onde isso entra". Não é a `lp-draft` (landing page de produto) nem a `wiki-smith` (que esta chama só para linkar a página e anotar a decisão).
metadata:
  version: 0.1.1
---

# estudo-html — um estudo vira uma página e uma decisão no wiki

O dono lê estudo numa página, não no terminal. A página fica no `.wiki/resources/` (versionada, linkada de uma página de tema), e a decisão vai para o texto do wiki.

## 1. Pesquisar

1. **Comece pelo `.wiki`:** `rg -n -i '<nome>' $CASA_REPO_PRINCIPAL/.wiki` mostra o que já sabemos e com o que comparar (Hermes, NATS, pi, Claude Code...). A pergunta de verdade quase sempre é "isso serve para nós e onde?".
2. **Leia a fonte primária:** o README, o código e o changelog, com a versão ou o commit. Para um repo do GitHub, o DeepWiki ajuda a ler a arquitetura. Para um pacote npm, `npm view <pkg> version description repository.url`.
3. **Separe fato de leitura:** o que a fonte diz, com link, e o que você conclui.
4. **Post de blog ou página traduzida é pista, não fonte:** ache o repo (`gh search repos "<nome>"`, busca por `github <termo do post>`) e leia o código com `gh api repos/<o>/<r>/contents/<dir> --jq '.[].name'` e `-H 'Accept: application/vnd.github.raw'` para o arquivo. O post parafraseia e erra nomes; o código dá a API real.
5. **"Study code" / "me traz o código" = responder com trechos reais da fonte**, cada um com o caminho do arquivo (`src/types.ts`, `test/examples/…`) e uma linha do que mostra; o exemplo executável do repo (pasta `examples/`, `test/examples/`) vale mais que o README. Diga se rodou ou só leu.
6. **Comparar vários frameworks:** escreva primeiro um arquivo de lente comum (as mesmas perguntas para todos) no scratch, e dispare um subagente por framework (até 8 em paralelo) com a lente, as fontes e um arquivo de saída por framework no mesmo formato (tabela + trecho real com URL + "ideia a roubar"). Sem lente comum, as respostas não se comparam. Para agentes/LLM, use a lente de [references/agent-app-layer-lens.md](references/agent-app-layer-lens.md). Se o dono pedir LP da comparação, a página sai pela `lp-draft`, não por esta.

## 2. Escrever a página

Copie `templates/estudo.html` (nesta pasta) para `$CASA_REPO_PRINCIPAL/.wiki/resources/<slug>.html` e preencha, nesta ordem:

1. **Veredito no topo**, em uma ou duas frases: usar, não usar, ou usar só para X, com o porquê.
2. **O que é**, em cartões curtos.
3. **A matriz de comparação** (`<table>`): critérios nas linhas, as opções nas colunas, uma palavra ou frase curta por célula. Quando o dono pedir "ASCII", a matriz vai também em texto monoespaçado, num bloco `<pre>`, e no `.wiki` em Markdown.
4. **Onde entra no nosso sistema**, com links para as páginas do `.wiki`.
5. **Fontes**, com a versão ou o commit.

- **Nada de Artifact nem de CDN:** um arquivo só, com o CSS inline e os tokens claro/escuro do template. O dono pediu HTML local.
- **Comparação pedida depois** ("cria outro comparando com o Hermes") vira outra página, `<slug>-vs-<outro>.html`, com link entre as duas.

## 3. Abrir

```sh
open -na "Google Chrome" --args --new-window "file://$CASA_REPO_PRINCIPAL/.wiki/resources/<slug>.html"
```

Sempre numa janela nova: a janela atual do Chrome é do dono.

## 4. Fechar no wiki

Com a skill `wiki-smith`:
- a decisão vai na página de tema, com o link `resources/<slug>.html`;
- uma nota no diário;
- commit e sync.

Um estudo que só existe no HTML se perde; a decisão precisa estar no texto do wiki.
