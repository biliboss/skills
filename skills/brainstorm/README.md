# brainstorm

Pensar junto com o dono quando a ideia ainda está aberta, antes do backbrief (o backbrief confirma uma tarefa que já
está clara). O quadro é o Double Diamond (descobrir, definir, desenvolver, entregar), com pensamento sistêmico onde
couber: Cynefin, iceberg, laço causal e pontos de alavanca. As regras estão no [SKILL.md](SKILL.md).

## Como funciona

1. Uma pergunta por vez, pela ferramenta de perguntas do harness; 2 a 3 abordagens com trade-offs e uma recomendação.
2. O agente anota cada passo no diário (`~/.local/share/brainstorm/events.jsonl`, ou `BRAINSTORM_DIR`).
3. O laço causal aparece no dev-console, no domínio Brainstorm: variáveis como nós, ligações com + ou −.
4. Sai uma nota curta, "Decidi X porque Y", que vai ao backbrief como a tarefa a confirmar.

| Comando | Exemplo |
|---|---|
| registrar um evento | `scripts/brainstorm.sh emit link.added '{"from":"pressa","to":"bugs","polarity":"+"}' --session s1 --actor bili` |
| listar sessões | `scripts/brainstorm.sh sessions --status started` |
| o laço causal em JSON | `scripts/brainstorm.sh graph s1` |

Testes: `uv run --script scripts/test_brainstorm.py`. Histórico: [CHANGELOG.md](CHANGELOG.md).
Fontes e o que foi tomado de cada uma: [references/prior-art.md](references/prior-art.md).

## Créditos e referências

Links conferidos com `curl -sIL` em 2026-11-06 (200 = abre).

| Base | Autor, obra, ano | Link | Verificação |
|---|---|---|---|
| Brainstorming | Alex F. Osborn, *Applied Imagination*, 1953 | https://en.wikipedia.org/wiki/Applied_Imagination | 200 |
| Double Diamond | UK Design Council, Double Diamond / Framework for Innovation, 2005 | https://www.designcouncil.org.uk/our-resources/framework-for-innovation/ | 200 |
| Diálogo do brainstorming (uma pergunta por vez, abordagens, aprovação por seções) | Jesse Vincent (obra/superpowers), skill `brainstorming`, MIT | https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md | 200 |
| Cynefin | Dave Snowden e Mary Boone, "A Leader's Framework for Decision Making", Harvard Business Review, 2007 | https://hbr.org/2007/11/a-leaders-framework-for-decision-making | 200 |
| Diagrama de laços causais, arquétipos R e B | Peter Senge, *The Fifth Discipline*, 1990 | https://en.wikipedia.org/wiki/The_Fifth_Discipline | 200 |
| Dinâmica de sistemas (laços de realimentação) | Jay W. Forrester, *Industrial Dynamics*, MIT Press, 1961 | https://en.wikipedia.org/wiki/Jay_Wright_Forrester (página do autor; a página da obra na Wikipedia dá 404 e a da MIT Press dá 403 ao curl) | 200 (autor) |
| Pontos de alavanca (12 níveis) | Donella H. Meadows, "Leverage Points: Places to Intervene in a System", 1999 | https://donellameadows.org/archives/leverage-points-places-to-intervene-in-a-system/ | 200 com cabeçalhos de navegador; 406 com `curl -A Mozilla/5.0` simples |
| Pensamento sistêmico (estoques, fluxos, laços) | Donella H. Meadows, *Thinking in Systems: A Primer*, Chelsea Green, 2008 | https://en.wikipedia.org/wiki/Donella_Meadows (página da autora; a página da editora dá 403 ao curl) | 200 (autora) |
| Modelo do iceberg (evento, padrão, estrutura, modelo mental) | **Atribuição incerta.** A metáfora do iceberg vem da cultura (Edward T. Hall, *Beyond Culture*, 1976) e a versão em quatro níveis circula na comunidade de pensamento sistêmico ligada a Senge e à Innovation Associates, sem uma obra única que eu tenha conseguido confirmar | sem link confiável (a página `Iceberg_model` da Wikipedia dá 404) | não verificado |

Não foi verificado: o conteúdo das páginas além do código HTTP (o HBR e a Design Council abrem; não li os textos
completos, que podem estar atrás de assinatura).
