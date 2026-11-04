# O cartão de um item

O cartão é o que o dono lê em cima à esquerda no focus e o que fica no done today. Quem escreve é a sessão do item, ao parar e de novo quando o estado muda. O arquivo é `~/.local/state/<tema>.cartao.md`, onde `<tema>` é o nome da aba.

## Formato

```markdown
# <o estado real, até ~60 caracteres: "Rodada 1 validada · rodadas 2 e 3 em validação">

## Bloqueio
<só quando houver: o que parou e até quando. "O validador do Claude Code parou no limite de 5 h; volta às 13:50.">

## Feito
- <um fato por linha, curto; tudo o que é informação mora aqui>

## Você confere
- <verbo + o que o dono faz: "Abra o [PR #121](<url>) e aprove a nota">
```

- **O título é o estado, não a meta.** Se metade está pronta, ele diz as duas metades. Nada de rótulo "Pronto" em cima de algo que não está pronto.
- **"Você confere" só com o que o dono faz,** cada item começando por verbo (abra, aprove, decida, responda). Um fato ("falta a régua", "a comparação não é limpa") vai para "Feito", e o que outro agente ainda vai fazer também.
- **"Bloqueio" só quando há um:** limite de conta, pergunta sem resposta, falha que parou o trabalho. O cartão o desenha em destaque.
- O título segue a régua do título de cartão do Linear: sem prefixo, sem jargão de agente, sem emoji. Sem caminho nem nome de ferramenta no texto; o link vai no item de "Você confere".

## O pedido para mandar à sessão

Mande pela fila, com `mux.sh fila <pane> <arquivo>`:

```
Escreva o seu cartão para o dono em ~/.local/state/<seu tema>.cartao.md (o seu tema é o nome da sua aba). É o que aparece em cima à esquerda no focus. Formato: <este arquivo>; estilo: .wiki/escrever-bem.md. Se ainda estiver trabalhando, escreva o estado de agora e reescreva quando terminar. Não mude mais nada.
```

## Como o cartão é desenhado

O `cartao.py` (rich) acha a própria aba pelo `HERDR_PANE_ID` e desenha só o resumo:

- a idade do arquivo ("atualizado há 2 min");
- o título em negrito;
- "Bloqueio" em destaque, em amarelo e negrito;
- cada `##` como rótulo em ciano forte e maiúsculas;
- o corpo em markdown, na largura do pane.

Ele redesenha a cada 15 s, num resize e quando a largura muda; com `--uma`, desenha uma vez. O nome, o estado e o harness do agente vão na barra (`barra.py`), não no cartão.
