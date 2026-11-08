# <Tema>: <a pergunta em uma linha>

**Objetivo:** <o resultado verificável, numa frase>.
**Janela:** <início> → <fim>, em UTC.

## Fontes e como acessar
- HyperDX: `mcpc @clickstack tools-list`; chame com `mcpc @clickstack tools-call <ferramenta> '<json>'`. Dentro do Python, monte o JSON com `json.dumps` e passe por `shlex.quote`, senão as aspas simples do SQL somem.
- <outra fonte, e como ler>
- Contexto (só leitura, só as seções que importam): <páginas do $WIKI_HOME/biliboss do repo da casa>

## Regras
- SÓ LEITURA. No HyperDX, nunca chame ferramenta `[destructive]` (`save_*`, `delete_*`, `patch_*`).
- Não edite nada fora desta pasta. Pacote Python (duckdb, pandas), só num `.venv` dentro desta pasta; nada global.

## Entrega
Escreva `<arquivo>.md` nesta pasta com:
- os achados, cada um com o número, a fonte (tile ou tabela) e a consulta exata que o produziu;
- o que fazer com cada achado;
- o que você não conseguiu medir, e por quê.
Depois, mostre aqui um resumo de até 10 linhas.
