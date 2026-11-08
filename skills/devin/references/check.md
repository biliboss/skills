# check: ver as rodadas

`scripts/check.sh [id]`

Uma linha por rodada, separada por tab: id, estado, segundos, branch, modelo. Sem id, lista todas. Não bloqueia.

Estados: `running`, `done`, `failed` e `lost` (o processo sumiu sem gravar a saída).
