# Changelog

## [0.2.0] - 2026-11-04

### Added
- O tipo **artigo do LinkedIn** no `SKILL.md` (regra 24 da voz): o objetivo no topo (o leitor se enxergar), nada técnico, uma imagem central simples, o exercício em texto e o fecho com uma pergunta que põe o leitor dentro da ideia.
- A ordem fixa: as imagens só são geradas depois do OK do texto no painel lateral, pela skill `faceless-art`; antes, só uma lista de ideias.
- As regras de imagem do artigo: a capa 1920 × 1080 (16:9), PNG ou JPG, nunca GIF, entendida pequena (oficial, com o link da ajuda do LinkedIn); 3 a 4 imagens no corpo, uma a cada ~250 palavras (opinião de praticante; o estudo de 2014 de Paul Shapiro no OkDork é correlação e antigo).
- A leitura do pedido: a analogia com que o dono explica a intenção é o porquê, não conteúdo.
- `templates/artigo.html`: o esqueleto do artigo aprovado ("A quarta sócia"), com marcadores.
- `references/experiencias.md`: um aprendizado por linha, datado, a partir das regras 12 a 24 da voz.
- `scripts/metricas.py`: a cópia do script de métricas de prosa do biliboss, rodado antes de mostrar um rascunho.

### Changed
- A arte passa a apontar para a skill `faceless-art`, e a publicação para a skill `linkedin-publish`, sem repetir o passo a passo.
- Os passos apontam também para as páginas `copywriting-estruturas` e `copywriting-metricas` da wiki.

## [0.1.0] - 2026-11-04

### Added
- Skill `copywriting`: o passo a passo para escrever um post do Gabriel (ler a wiki e os docs do Linear, rascunho no painel lateral, arte por subagente, OK, Linear), apontando para `.wiki/marketing-pessoal-voz.md` do biliboss como fonte das regras.
