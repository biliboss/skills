# clean: remover uma rodada

`scripts/clean.sh <id> [--force]`

Remove worktree, branch e estado. Recusa rodada ativa (`running` ou `starting`) sempre. Sem `--force`, recusa alterações sem commit, arquivos novos ou ignorados, commits fora do `HEAD` do repositório e tudo o que não conseguir verificar (git falhando, repositório sumido, worktree quebrado). Com `--force` sempre termina. O `meta.env` só vale se `WORKTREE` for `<pasta>/wt` e `BRANCH` for `devin/<id>`; senão a limpeza é recusada. Use `--force` só depois de decidir descartar o trabalho.
