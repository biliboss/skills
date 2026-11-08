# devin

Delega uma tarefa de código ao Devin CLI em background: um worktree e um branch por tarefa, SWE-2 Max por padrão, e revisão do diff antes de aceitar. Cada verbo tem um guia em [references/](references/) e responde a `--help`; o histórico, em [CHANGELOG.md](CHANGELOG.md).

## Como funciona

1. `run.sh` cria o worktree, dispara o Devin destacado do shell e devolve um id.
2. `wait.sh` ou `check.sh` acompanham a rodada.
3. `review.sh` mostra a resposta e o que mudou.
4. Depois de integrar o branch, `clean.sh` remove tudo.

## Scripts

| Script | O que faz | Exemplo |
|---|---|---|
| `run.sh` | Dispara uma rodada e imprime o id | `scripts/run.sh --repo ~/src/app --prompt-file /tmp/pedido.md --name corrige-login` |
| `check.sh` | Lista as rodadas ou mostra uma | `scripts/check.sh` |
| `wait.sh` | Bloqueia até o fim e sai com o código do Devin | `scripts/wait.sh <id> --timeout 1800` |
| `review.sh` | Resposta, commits, diff e arquivos novos | `scripts/review.sh <id>` |
| `clean.sh` | Remove worktree, branch e estado | `scripts/clean.sh <id>` |
| `batch.sh` | Roda um script `.mjs` que dispara vários Devins, sem gastar tokens enquanto esperam | `scripts/batch.sh --repo ~/src/app --max 3 revisa.mjs` |

## Configuração

Copie `example.env` para `.env` ao lado do `SKILL.md`. Todas as chaves são opcionais.

## Testes

Sem suíte automática. A 0.2.0 foi verificada com um `DEVIN_BIN` falso (um script `sh` que dorme, escreve arquivos ou sai com código) e com uma rodada real no `swe-2-medium`.
