# wait: ser avisado sem travar a conversa

`scripts/wait.sh <id> [--timeout <segundos>]`

Bloqueia até a rodada terminar. Rode sempre em background no harness (`run_in_background`), nunca em primeiro plano: o harness avisa quando ele sai, e a conversa segue livre. Uma espera por rodada; `--timeout 1800` é um bom começo.

| Saída | Significado |
|---|---|
| código do Devin | a rodada terminou; 0 é sucesso |
| 124 | prazo esgotado; a rodada continua |
| 1 sem código gravado | processo perdido |
| 2 | erro de uso: `--timeout` não numérico ou negativo, argumento extra |

Quem decide é o estado impresso na saída (`done`, `failed`, `lost`), não só o código: um Devin que saia com 124 colide com o código de prazo, e nesse caso o estado impresso é `failed`.

O Devin continua se a sessão que disparou fechar; só o aviso se perde. Veja o estado com [check](check.md). Ao receber o aviso, siga para [review](review.md).
