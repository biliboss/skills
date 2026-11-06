# search-console

Lê o Google Search Console de um site por uma conta de serviço só de leitura: as propriedades, as consultas e
páginas com cliques, impressões, CTR e posição, os sitemaps e o status de indexação de uma URL. A saída é JSON, pelo
`scripts/gsc.sh`.

É a skill que o perfil `via-ads` do Hermes (o agente de anúncios e busca da Via Corretor) usa para a busca orgânica.

Para usar em outro site: uma conta de serviço com a API do Search Console ligada, a chave em `GSC_KEY`, a propriedade
em `GSC_SITE`, e o e-mail da conta adicionado como usuário da propriedade no Search Console.

As regras para o agente estão no [SKILL.md](SKILL.md); a história, no [CHANGELOG.md](CHANGELOG.md).
