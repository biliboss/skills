# Receita: sugestões a partir do HyperDX

O caso que já rodou e funcionou: o Prime Agent lê os painéis do HyperDX só por leitura e devolve 3 sugestões acionáveis, cada uma com o número, o tile de onde veio e a consulta exata. Leva uns 6 minutos; o `glm-5.3-flash` basta, porque o trabalho pesado é a consulta, não o raciocínio.

## 1. Abrir

```sh
S/abrir.sh hyperdx glm-5.3-flash      # o pane à direita, em $PRIME_LAB/hyperdx
```

## 2. O briefing (`$PRIME_LAB/hyperdx/BRIEF.md`)

Parta do `templates/BRIEF.md` e preencha assim:

- **Objetivo:** ler o HyperDX e propor 3 sugestões concretas e acionáveis, cada uma com "o que viu", "a evidência" (números + consulta) e "o que fazer", com a meta que diria que deu certo.
- **Janela:** as últimas 48 h, com o início e o fim em UTC escritos no arquivo (ele calcula com `datetime`, mas a janela fixa deixa a conferência repetir a mesma conta).
- **Fontes:** comece por `clickstack_list_sources` e pelos painéis que o `hyperdx-paineis.md` do repo da casa lista (os ids estão lá, não aqui). Para um painel, `clickstack_query_tiles` primeiro (todos os tiles, para ver quais têm dado) e `clickstack_query_tile` depois, nos que importam; para citar a consulta, `clickstack_get_dashboard_tile`; para o que nenhum tile responde, `clickstack_sql` com o `connectionId` da fonte.
- **Contexto:** as seções de `hyperdx-paineis.md` e `hyperdx-recursos.md` sobre os painéis usados (não as páginas inteiras: ele imprime o arquivo todo e gasta ~20 mil tokens à toa).
- **Entrega:** `sugestoes.md` na pasta, mais "Outros achados" (medidos, sem sugestão formal) e a lista das ferramentas chamadas, para provar que foi só leitura.

## 3. O padrão que ele monta (diga no briefing para poupar voltas)

- Uma função para tile que devolve só o `result` (o JSON vem entre crases quádruplas na saída do `mcpc`; extraia com regex e `json.loads`).
- Uma função `sql(q)` com o JSON passado por `shlex.quote`: sem isso as aspas simples do SQL somem no shell.
- Sem `FORMAT ...` no SQL: o `clickstack_sql` já embrulha a consulta e recusa.
- `await` só no nível da célula ou dentro de `async def`.
- Várias consultas disparadas antes de esperar (um dicionário de tarefas), e as contas (`statistics.median`, p90, quantos passam da meta) feitas no Python.

## 4. Conferir antes de usar

Rode de novo, direto com o `mcpc`, as 2 ou 3 consultas que sustentam as sugestões, com a mesma janela: um número de tile (`clickstack_query_tile`) e um total por SQL (`count()`, `countIf`, `sumIf`) costumam bastar. Confira também as contas que ele fez por cima (razões e "x vezes mais barato"): é aí que ele erra.

## 5. Fechar

- O wiki do repo da casa: a página `prime-agent-hyperdx.md` (ou `prime-agent-<tema>.md` para um tema novo), ligada no `moc-prime-agent`, com os achados numa tabela (o número e de onde veio), o que foi conferido e o que foi para quem.
- O que é da VPS (tile, alerta, coletor, o próprio Bili) vira **um cartão de resultado com os achados como checklist**, no projeto e no marco certos, para o Bili (skills `linear` e `bili`). O que é das sessões do Mac fica com o dono.
- As consultas que vão se repetir são candidatas a um script do repo da casa, para o próximo ciclo não começar do zero.
