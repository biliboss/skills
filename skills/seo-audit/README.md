# seo-audit

Audita o SEO de um site lendo o HTML como ele chega, sem JavaScript, e os sitemaps declarados no robots.txt. Não
muda nada. Cada página sai com os fatos (status, redirecionamentos, título, descrição, canonical, noindex, h1, lang,
Open Graph, JSON-LD, imagens sem alt) e os achados, cada um marcado como erro, aviso ou info.

Foi feita para o agente de anúncios e busca da Via Corretor (perfil `via-ads` do Hermes), e serve para qualquer site.

## Como funciona

1. `audit.sh` baixa cada URL, segue os redirecionamentos anotando a cadeia e lê o HTML.
2. Quando o canonical aponta para outra URL, abre essa URL também, para saber se ela redireciona de volta (o
   `canonical-loop`) ou se está quebrada.
3. `sitemap.sh` acha os sitemaps no robots.txt (ou tenta `/sitemap.xml`), segue os índices e lista as URLs; com
   `--check`, abre cada uma e agrupa as que redirecionam.

## Scripts

| Script | O que faz | Exemplo |
|---|---|---|
| `scripts/audit.sh` | fatos e achados de uma ou mais páginas | `audit.sh https://viacorretor.com.br/blog/como-tirar-creci` |
| `scripts/sitemap.sh` | os sitemaps do site e, com `--check`, o status de cada URL | `sitemap.sh viacorretor.com.br --check` |
| `scripts/test.sh` | teste offline com fixtures, numa porta local própria | `test.sh` |

Precisa do `uv` (o Python é só da biblioteca padrão) e, nos testes, do `jq` e do `curl`.

As regras para o agente estão no [SKILL.md](SKILL.md); de onde vieram as ideias, em
[references/prior-art.md](references/prior-art.md); a história, no [CHANGELOG.md](CHANGELOG.md).
