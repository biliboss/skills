# clean: remover uma rodada

`scripts/clean.sh <id> [--force]`

Remove worktree, branch e estado. Recusa rodada ativa sempre. Sem `--force`, recusa alterações sem commit e commits fora do `HEAD` do repositório. Use `--force` só depois de decidir descartar o trabalho.
