# memory

Reduz um agente (todas as sessões da pasta dele) ou uma sessão a um `facts.jsonl` pequeno e buscável: decisões, preferências, correções, fatos duráveis e pedidos em aberto. O modelo julga cada janela da conversa; o código confere cada fato contra a mensagem de origem e guarda só o que passa.

## Como funciona

1. Lê a sessão, mascara segredos e dados pessoais e separa as falas do dono.
2. Corta o que é novo em janelas de N falas do dono.
3. O Devin propõe os fatos de cada janela.
4. Proposta com violação volta para correção; proposta válida é absorvida e o cursor avança.

Opções e exemplos estão no [SKILL.md](SKILL.md). O prompt está em [resources/prompt.md](resources/prompt.md) e o contrato do domínio em [scripts/interface.ts](scripts/interface.ts).

| Script | Exemplo |
|---|---|
| `scripts/memory.ts` | `bun run scripts/memory.ts <pasta do agente> --last 10` |

Histórico: [CHANGELOG.md](CHANGELOG.md).

## Limite conhecido

O `onPermission` restringe leitura, escrita e shell, mas não foi acionado no primeiro teste real. Não conte com ele como barreira até isso ser verificado.
