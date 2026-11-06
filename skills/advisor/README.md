# advisor

O agente principal (o Bili no Sonnet) pede uma segunda opinião a uma sessão mais forte, o advisor (Opus), nos pontos em que o julgamento pesa, e aprende com um diário quando vale chamar. A sessão advisor não executa nada: lê o contexto e devolve um veredito curto.

O comportamento completo, para o agente, está em [SKILL.md](SKILL.md). Esta página é para quem lê o repositório.

## Como funciona

1. Antes de um ponto de consulta, o agente lê o diário: `scripts/decisions.sh recent <task_kind> --moment <ponto>` diz CHAME ou PULE.
2. Chamando, grava a pergunta com `scripts/ask.sh ask` (o contexto vai para `~/.local/share/advisor/`) e avisa a sessão advisor pelo SendMessage.
3. O advisor responde com `scripts/ask.sh reply`: veredito `segue`, `corrige` ou `para`.
4. O agente segue o veredito e grava como foi, com `scripts/rate.sh`.

Os pontos de consulta são o plano, travar, entregar, algo difícil de desfazer ou que sai para fora, e um pedido ambíguo. Fora deles, o agente segue sozinho.

## Os scripts

| Script | Para quê | Exemplo |
|---|---|---|
| `ask.sh` | a pergunta, o veredito, um fato, a thread | `ask.sh ask minha-tarefa --task ... --question ...` |
| `decide.sh` | uma decisão, chamando ou não | `decide.sh minha-tarefa --moment plano --called true --task-kind codigo --reason ...` |
| `rate.sh` | o que veio da decisão: `rated` ou `missed` | `rate.sh rated minha-tarefa <id> --moment plano --changed-course true --useful true --note ...` |
| `decisions.sh` | o resumo que diz CHAME ou PULE | `decisions.sh recent codigo --moment plano` |
| `test.sh` | os 21 casos, num diretório temporário | `scripts/test.sh` |

Os arquivos só recebem linhas novas, e cada linha tem até 3500 bytes. O que é maior vai para `resources/<thread>/`. `ask.sh` recusa copiar `.env`, chave, token e `.sesskey`.

## Onde ficam os dados

`~/.local/share/advisor/` (ou `$ADVISOR_DIR`):

- `context.jsonl`: as perguntas, os vereditos e os fatos, por thread.
- `decisions.jsonl`: o diário de chamar ou não.
- `resources/<thread>/`: o que não cabe numa linha.

## Rodar o teste

```sh
scripts/test.sh
```

Roda num diretório temporário e nunca toca em `~/.local/share/advisor/`.

## História

[CHANGELOG.md](CHANGELOG.md).
