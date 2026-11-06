# handoff

A passagem de turno de um agente Hermes no tmux: a sessão comprida é registrada, vira um branch numa aba à direita e
só então a aba original começa do zero, com um resumo de onde ficou tudo. Regras e uso: [SKILL.md](SKILL.md).

| Comando | O que faz |
|---|---|
| `handoff.sh [<alvo tmux>] [--from ID]` | registra, faz o branch à direita e limpa a original (só com o branch pronto) |
| `handoff.sh log [N]` | as últimas N sessões passadas, com `hermes -p bili --resume <id>` |

Registro: `~/.local/state/bili-sessions.jsonl`. Testes: `scripts/test.sh` (tmux privado, hermes falso da skill thread).

## Créditos e referências

- O nome: a passagem de turno (handoff) da enfermagem (SBAR, I-PASS) e do controle de tráfego aéreo.
- O fork offline e o Value Object `thread()`: a skill [thread](../thread/).
