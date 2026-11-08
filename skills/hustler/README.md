# hustler

A routine for seeing the market around an idea and finding where to stand in it: the customer's job, the real
alternatives, a positioning map with an empty (or crowded) upper quadrant, and the business model options. It is
built to be re-run: each run starts from the last page and goes one step further.

## Como funciona

1. Uma linha: o trabalho e o cliente.
2. As alternativas reais (concorrentes, código aberto, não fazer nada), com fonte.
3. Dois eixos que importam para o cliente e o mapa de posicionamento.
4. Onde fica o quadrante superior e o que falta para chegar lá.
5. Os modelos de negócio, incluindo open-core, e quem paga o quê.
6. Uma página na wiki do projeto (skill `wiki`), o HTML do mapa e a lista do que rever na próxima vez.

As regras estão no [SKILL.md](SKILL.md); aqui não se repetem.

## Scripts

| Script | O que faz | Exemplo |
|---|---|---|
| `scripts/render-map.sh <json> <html>` | gera o mapa de posicionamento (HTML com SVG embutido, tabela, achados, modelos, fontes) a partir do JSON do projeto | `render-map.sh $WIKI_HOME/<projeto>/resources/hustler-zelito.json $WIKI_HOME/<projeto>/resources/hustler-zelito.html` |

Forma do JSON: `title, job, customer, x_label, y_label, upper_label, items[{name, x, y, kind, note, price, src}], findings,
models[{name, who_pays, what}], recheck, sources[{label, url}]` (notas de 0 a 10; `kind` é `alt`, `nothing`, `us` ou
`target`). Primeiro uso: o mapa do Zelito.

Testes: `uv run --script scripts/render_map.py <json> /dev/stdout` deve sair com código 0 num JSON válido e com 1 se faltar
um campo ou uma nota sair de 0 a 10.

Histórico: [CHANGELOG.md](CHANGELOG.md).

## Créditos e referências

Links conferidos com `curl -sIL` (cabeçalho de navegador) em 2026-11-06; 200 = abre.

| Base | Autor, obra, ano | Link | Verificação |
|---|---|---|---|
| Mapa de percepção / de posicionamento (perceptual mapping) | técnica de pesquisa de marketing; sem autor único confirmado por mim | https://en.wikipedia.org/wiki/Perceptual_mapping | 200 |
| "Quadrante superior direito" (Leaders: visão completa × capacidade de execução) | Gartner, Magic Quadrant | https://en.wikipedia.org/wiki/Magic_Quadrant; FAQ do Gartner: https://gartner.com/en/about/magic-quadrant-faq | 200; o FAQ dá 403 ao curl, abre no navegador (li o trecho pela busca) |
| Oceano azul: as quatro ações (eliminar, reduzir, elevar, criar) e o canvas estratégico | W. Chan Kim e Renée Mauborgne, "Blue Ocean Strategy", Harvard Business Review, 2004 | https://hbr.org/2004/10/blue-ocean-strategy | 200 |
| Jobs to Be Done | Clayton Christensen, Taddy Hall, Karen Dillon, David Duncan, "Know Your Customers' Jobs to Be Done", Harvard Business Review, 2016 | https://hbr.org/2016/09/know-your-customers-jobs-to-be-done | 200 |
| Teses de investidores | Y Combinator, Requests for Startups | https://www.ycombinator.com/rfs | 200 |
| Open-core | termo de Andrew Lampitt, "Open-Core Licensing (OCL)", 2008 (arquivo da web) | https://web.archive.org/web/20241220103330/https://alampitt.typepad.com/lampitt_or_leave_it/2008/08/open-core-licen.html; resumo: https://en.wikipedia.org/wiki/Open-core_model | 200 (li o resumo da Wikipedia, não o texto de Lampitt) |
| Modelos de negócio de software aberto | Wikipedia, Business models for open-source software | https://en.wikipedia.org/wiki/Business_models_for_open-source_software | 200 |

Não verificado: o texto completo do HBR e do Gartner (podem estar atrás de assinatura); a autoria do mapa de percepção.
