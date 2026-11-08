# devin

Delega uma tarefa de código ao Devin CLI em background: um worktree e um branch por tarefa, SWE-2 Medium por padrão, lotes de até 8 em paralelo com gates por fora do Devin, e revisão do diff antes de aceitar. Cada verbo tem um guia em [references/](references/) e responde a `--help`; o histórico, em [CHANGELOG.md](CHANGELOG.md).

## Como funciona

1. `run.sh` cria o worktree, dispara o Devin destacado do shell e devolve um id.
2. `wait.sh` ou `check.sh` acompanham a rodada.
3. `review.sh` mostra a resposta e o que mudou.
4. Depois de integrar o branch, `clean.sh` remove tudo.

Em lote ([references/lote.md](references/lote.md)): `batch.sh` dispara os cartões de um manifesto, `gate.sh` confere escopo e gates por fora do Devin, `retry.sh` repete no mesmo worktree e `merge.sh` integra a fila.

## Scripts

| Script | O que faz | Exemplo |
|---|---|---|
| `run.sh` | Dispara uma rodada e imprime o id | `scripts/run.sh --repo ~/src/app --prompt-file /tmp/pedido.md --name corrige-login` |
| `check.sh` | Lista as rodadas ou mostra uma | `scripts/check.sh` |
| `wait.sh` | Bloqueia até o fim e sai com o código do Devin | `scripts/wait.sh <id> --timeout 1800` |
| `review.sh` | Resposta, commits, diff e arquivos novos | `scripts/review.sh <id>` |
| `clean.sh` | Remove worktree, branch e estado | `scripts/clean.sh <id>` |
| `batch.sh` | Dispara um manifesto de cartões, no máximo `DEVIN_MAX_PARALLEL` (8) rodando, e imprime os ids; rode em background | `scripts/batch.sh lote.json --repo ~/src/app` |
| `gate.sh` | Escopo contra `allowed` e gates (prek) nos arquivos alterados; exit 0 aprovado, 1 reprovado, 2 não pôde rodar | `scripts/gate.sh <id>` |
| `retry.sh` | Nova tentativa no mesmo worktree, arquivando a anterior; no máximo 2 | `scripts/retry.sh <id> --prompt-file /tmp/pedido2.md` |
| `merge.sh` | Integra os ids na ordem, um por vez, com gates depois de cada merge; nunca faz push | `scripts/merge.sh --into ~/src/app.integra --message-file msg.txt <id>...` |

`_gates.sh` é interno (gate.sh e merge.sh o chamam). Os gates copiáveis, com a catraca para o legado, estão em [templates/gates/](templates/gates/README.md).

## Configuração

Copie `example.env` para `.env` ao lado do `SKILL.md`. Todas as chaves são opcionais (`DEVIN_MAX_PARALLEL`: teto de rodadas simultâneas, padrão e máximo 8).

## Testes

Esta versão ainda não tem testes. A verificação do lote é reproduzível com um Devin falso (`DEVIN_BIN`) e repositórios temporários; ver o CHANGELOG.
