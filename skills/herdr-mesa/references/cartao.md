# O cartão de um item

O cartão é o que o dono lê à esquerda do agente no focus e o que fica no done today. Quem escreve é a sessão do item, ao parar (e de novo quando o estado muda). O arquivo é `~/.local/state/<tema>.cartao.md`, onde `<tema>` é o nome da aba.

## Formato

```markdown
# <o resultado visível, até ~55 caracteres>

## Pronto
<Você abre X e vê Y. Uma ou duas frases.>

## Feito
- <um fato por linha, curto>

## Você confere
- [<nome do link>](<url>)
- <a decisão ou o que falta do dono>
```

O título segue a régua do título de cartão do Linear (o resultado, sem prefixo, sem jargão de agente, sem emoji). Sem número de PR, caminho ou nome de ferramenta no texto; o link vai em "Você confere".

## O pedido para mandar à sessão

Mande por arquivo, com `herdr-agentes/scripts/agente.sh manda <pane> <arquivo>`:

```
Escreva o seu cartão para o dono em ~/.local/state/<seu tema>.cartao.md (o seu tema é o nome da sua aba). É o que aparece à esquerda de você no workspace focus. Formato e estilo: <este arquivo> e o .wiki/escrever-bem.md. Se ainda estiver trabalhando, escreva o estado de agora e reescreva quando terminar. Não mude mais nada.
```

## Como o cartão é desenhado

`cartao.py` (rich) acha a própria aba pelo `HERDR_PANE_ID`, lê o rótulo da aba e desenha: o tema e o estado de cada pane do item, depois o título em negrito, cada `##` como rótulo apagado em maiúsculas e o corpo em markdown, na largura do pane. Redesenha a cada 15 s; `--uma` desenha uma vez.
