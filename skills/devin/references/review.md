# review: revisar o que o Devin fez

`scripts/review.sh <id>`

Mostra estado, branch, worktree, base, resposta, commits, diff resumido e arquivos novos. Em falha, acrescenta o fim do log. Sem `meta.env`, sem git funcional no worktree ou com a base inalcançável, o relatório segue e marca o que faltou.

O relatório do Devin é uma afirmação; o diff é a evidência. Antes de aceitar:

1. Leia o diff inteiro: `git -C <worktree> diff <base>`.
2. Rode a verificação você mesmo.
3. Integre o branch `devin/<id>`, conferindo se ficou alteração sem commit no worktree.

Depois, [clean](clean.md).
