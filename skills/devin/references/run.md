# run: disparar uma rodada

`scripts/run.sh --repo <caminho> --prompt-file <arquivo> [--name <slug>] [--model <m>] [--mode <permissão>] [--base <ref>]`

Cria um worktree no branch `devin/<id>`, dispara o Devin destacado e imprime só o id. Retorna na hora: continue trabalhando e siga com [wait](wait.md). `--stdin` lê o pedido da entrada padrão; sem ele, o stdin nunca é lido.

## Antes de disparar

- O conteúdo do worktree vai para a Cognition. Repositório sensível ou de cliente só com decisão do dono.
- Escreva o pedido num arquivo fora do repositório: resultado esperado, arquivos relevantes, como provar que funcionou, o que não mexer.

## Opções

| Opção | Padrão | Regra |
|---|---|---|
| `--model` | `swe-2-max` | Sem custo por token no Pro, sujeito às cotas. Modelo pago só a pedido do dono. |
| `--mode` | `accept-edits` | `smart` quando precisar rodar comandos. `dangerous` é recusado. |
| `--base` | `HEAD` | Para continuar uma rodada: `--base devin/<id>`, com o contexto no novo pedido, porque `-p` responde e sai. |

O checkout de origem fica intacto, e arquivos não rastreados, como `.env`, não entram no worktree. Rodadas podem ser paralelas.

Saída: 0 disparou, 1 erro, 2 uso. Os padrões vêm do `.env` ao lado do `SKILL.md`; modelo em `example.env`.
