# hire

O verbo para um agente criar e cuidar dos bots companheiros no Herdr, sempre a pedido do dono. As regras estão no
[SKILL.md](SKILL.md); o histórico, no [CHANGELOG](CHANGELOG.md).

## Como funciona

1. O agente redige a identidade do companheiro e mostra ao dono.
2. Com o ok, `hire.py` gera a sessão, cria a pasta e registra o bot no `bots.json`.
3. O Bots relê o registro em até 5 segundos, e o bot abre no próprio workspace.

Depende de `skills/bili-agents/scripts/bots.py`, que valida o registro e abre as sessões.

## Comandos

| Comando | Exemplo |
|---|---|
| Contratar | `scripts/hire.py new revisor "Revisor" --brief /caminho/brief.md` |
| Listar | `scripts/hire.py list` |
| Ajustar | `scripts/hire.py update revisor --name "Revisora" --brief /caminho/brief.md` |
| Aposentar | `scripts/hire.py retire revisor --confirm` |

O bot marcado com `"principal": true` no `bots.json` nunca pode ser aposentado. Aposentar não apaga a pasta nem a
conversa.

## Testes

```sh
python3 scripts/test_hire.py
```

Usam registro temporário e um `hc` falso; não tocam em terminais reais.
