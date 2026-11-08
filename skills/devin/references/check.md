# check: ver as rodadas

`scripts/check.sh [id]`

Uma linha por rodada, separada por tab: id, estado, segundos, branch, modelo. Sem id, lista todas. Não bloqueia.

Estados: `starting` (largada em curso; vira `lost` se passar de 60 s sem o worker aparecer), `running` (o worker ou o Devin ainda vive, mesmo órfão), `done`, `failed` (inclui o encerrado por `kill`) e `lost` (nada vivo e sem saída gravada). Rodada com `meta.env` ilegível aparece com `-` nos campos que faltam.
