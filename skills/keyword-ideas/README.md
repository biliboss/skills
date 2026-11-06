# keyword-ideas

Acha o que mirar na busca usando fontes grátis, sem mudar nada:

- `suggest.sh` pergunta ao autocompletar do Google, em português, o que as pessoas digitam depois de uma semente.
- `opportunities.sh` lê o nosso Search Console, pela skill `search-console`. Lista as consultas em que estamos quase
  na primeira página e as consultas e páginas que aparecem muito e quase não recebem clique.

Foi feita para o agente de anúncios e busca da Via Corretor (perfil `via-ads` do Hermes).

## Como funciona

1. `suggest.sh "corretor de imóveis"` devolve as sugestões do Google. Com `--expand`, também as da semente seguida de
   cada letra e as das palavras de pergunta antes dela (como, quanto, qual…). Fica só o que contém a semente.
2. `opportunities.sh` roda o `gsc.sh` da skill search-console duas vezes, por consulta e por página, e filtra:
   posição de 4 a 20 (quase lá) e posição até 10 com CTR baixo (aparece e não recebe clique).

## Scripts

| Script | O que faz | Exemplo |
|---|---|---|
| `scripts/suggest.sh` | o autocompletar do Google para as sementes | `suggest.sh creci --expand` |
| `scripts/opportunities.sh` | as oportunidades no nosso Search Console | `opportunities.sh --days 28 --min-impressions 10` |
| `scripts/test.sh` | teste offline, com um gsc.sh falso e o autocompletar de um arquivo local | `test.sh` |

Precisa do `uv` (o Python é só da biblioteca padrão) e da skill `search-console` para o `opportunities.sh`. Nos
testes, do `jq` e do `curl`.

As regras para o agente estão no [SKILL.md](SKILL.md); de onde vieram as ideias, em
[references/prior-art.md](references/prior-art.md); a história, no [CHANGELOG.md](CHANGELOG.md).
