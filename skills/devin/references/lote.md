# lote: vários cartões em paralelo, validados por gates

Ciclo: o Opus decompõe e escreve os cartões; o Devin executa; os gates e o Opus validam por fora; o `merge.sh` integra. Nenhum passo depende de teste: a prova é o gate mais o comando de prova do cartão, rodado pelo Opus.

```
manifesto -> batch.sh (background) -> wait.sh por id (background + Monitor) -> gate.sh -> review.sh e diff -> merge.sh -> clean.sh
                                                          reprovou: retry.sh
```

## Manifesto

JSON, um array de cartões. `prompt_file` relativo vale a partir da pasta do manifesto.

```json
[
  {"name": "corrige-login", "prompt_file": "cards/corrige-login.md", "allowed": ["src/login.py", "src/auth/*.py"]},
  {"name": "migra-config", "prompt_file": "cards/migra-config.md", "allowed": ["src/config/**"], "model": "swe-2-medium"}
]
```

- `name`: slug único (a-z, 0-9, hífen, até 40). Vira parte do id e do assunto do commit.
- `allowed`: lista fechada, relativa ao repositório, sem `..`. Caminho exato ou glob simples: `*` não atravessa `/`, `**` atravessa, `?` é um caractere.
- `model`: opcional; o padrão é `swe-2-medium`.

Dois cartões do mesmo lote não tocam o mesmo arquivo. Tipo, schema e configuração compartilhados vão no lote 0. O `batch.sh` avisa no stderr quando a mesma entrada de `allowed` aparece em dois cartões (e segue); glob que se sobrepõe a outro caminho ele não detecta.

## Disparar

`scripts/batch.sh lote.json --repo <repo> [--base <ref>] [--mode <permissão>]`

Valida tudo antes de disparar (nada dispara se algo falha), resolve a base para um sha uma vez e usa o mesmo em todos, e imprime cada id assim que dispara. O teto `DEVIN_MAX_PARALLEL` (padrão 8, máximo 8; não numérico ou menor que 1 é recusado) conta as rodadas `running` de todo o `DEVIN_RUNS_DIR`, não só as do lote: sem vaga, o script espera com `sleep 2`. Por isso ele demora e roda sempre em background no harness (`run_in_background`), lendo os ids pela saída. Cada `allowed` vai para `$dir/allowed`, um por linha.

## Esperar

`scripts/wait.sh <id>` em background, um por id, avisado por Monitor. Nunca laço com `sleep` em primeiro plano. `check.sh` mostra o estado de todas as rodadas.

## Cartão

Arquivo fora do repositório, autossuficiente (o Devin em `-p` não acessa Knowledge, Playbooks nem Secrets, e não lê imagem):

```
Objetivo: um resultado, em uma frase.
Contexto: invariantes e decisões que ele precisa saber.
Arquivos permitidos: lista fechada (a mesma do manifesto).
Não mexer: o que parece tentador e está fora.
Regras: não criar arquivos fora da lista; não rodar git; sem versão nem CHANGELOG.
Prova: comando que sai 0. Só texto, nunca screenshot.
Final: até três linhas e a lista do que ficou sem resolver.
```

## Validar

`scripts/gate.sh <id>`, por fora do Devin. Recusa rodada `running`. Confere o escopo (arquivos alterados contra a base: commits, staged, unstaged e não rastreados não ignorados) com `allowed` e roda o prek nos arquivos alterados, no estágio pre-commit e no pre-push, sem precisar de commit. Sem arquivo alterado, reprova. Grava `$dir/gate.txt`. Saída: 0 aprovado, 1 reprovado, 2 não pôde rodar (sem `.pre-commit-config.yaml` ou sem `prek`: nunca passa em silêncio). Os gates não modificam arquivos. Modelo copiável em [templates/gates](../templates/gates/README.md).

Depois do gate, o Opus lê o diff inteiro contra o cartão e roda a prova do cartão ([review](review.md)).

## Retentativa

`scripts/retry.sh <id> --prompt-file <arquivo> [--model <m>]`

Roda no mesmo worktree e no mesmo branch, sem criar outro. Os cartões proíbem git, e `--base` não levaria uma alteração que não foi commitada; por isso a nova tentativa enxerga o que a anterior deixou. O pedido novo leva a saída do gate ou o apontamento do review. Pedido, resposta, log, saída e gate da tentativa anterior vão para `$dir/attempts/<n>/`. A primeira retentativa usa `swe-2-medium`, a segunda `swe-2-max`; a terceira é recusada mesmo com `--model`: o Opus recorta o cartão.

## Integrar

`scripts/merge.sh --into <worktree> --message-file <arquivo> <id>...`

Os ids na ordem do grafo. Só integra, nunca faz push. Antes de começar recusa `--into` sujo ou em detached HEAD e qualquer id que não esteja `done`. Para cada id, um por vez: re-confere o escopo, commita o trabalho no branch `devin/<id>` (assunto `devin: <cartão>`, corpo = o message-file, onde vão os trailers de atribuição), faz `git merge --no-ff` no `--into` e roda os gates sobre os arquivos que entraram. Stdout: uma linha por id integrado.

- Conflito: `merge --abort`, o stderr diz qual id conflitou, em quais arquivos, e quais ficaram na fila; exit 1. O Opus resolve (ou recorta) e chama de novo com o que restou.
- Gate reprovado depois do merge: a fila para e o merge fica no `--into`; exit 1.

Depois: `doctor --gate` na main integrada, o fluxo real, e `clean.sh <id>` só então.
