# hire

Contrata um bot companheiro no Herdr, a pedido do dono. As regras estão no [SKILL.md](SKILL.md); o histórico, no
[CHANGELOG](CHANGELOG.md). Os outros verbos do ciclo são `roster`, `rebrief` e `fire`; o registro e a proteção do bot
principal ficam em `skills/bili-agents/scripts/bots.py`.

| Comando | Exemplo |
|---|---|
| Contratar | `scripts/hire revisor "Revisor" --brief /caminho/brief.md` |
| Sem abrir | `scripts/hire revisor "Revisor" --brief /caminho/brief.md --no-open` |

Testes: `python3 scripts/test_hire.py`. Usam registro temporário e um `hc` falso.
