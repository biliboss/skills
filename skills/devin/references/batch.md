# batch: vários Devins por um script, sem gastar tokens

`scripts/batch.sh --repo <caminho> [--max N] [--args <json>] <script.mjs>`

Roda um script de orquestração enquanto os Devins trabalham, sem gastar tokens do Claude. **Rode sempre em background no harness** (`run_in_background`): o aviso chega quando ele sai. Stdout traz só o resultado final em JSON; o progresso vai para stderr. Saída: 0 ok, 1 alguma etapa falhou, 2 uso ou script fora do subconjunto.

Vale o mesmo aviso do [run](run.md): o conteúdo do repositório vai para a Cognition. Cada `agent()` é uma rodada (worktree e branch próprios) com o modelo padrão do `.env`.

## O script

Mesma sintaxe dos scripts de workflow do Claude, só este subconjunto. O corpo roda dentro de uma função assíncrona: `await` e `return` de topo funcionam. O `export const meta = {...}` (literal puro, com `name` e `description`) é lido antes e tirado do corpo.

```js
export const meta = { name: 'review-changes', description: '...', phases: [{ title: 'Review' }, { title: 'Verify' }] }
const results = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, {label: `review:${d.key}`, phase: 'Review', schema: FINDINGS_SCHEMA}),
  review => parallel(review.findings.map(f => () =>
    agent(`Verify: ${f.title}`, {label: `verify:${f.file}`, phase: 'Verify', schema: VERDICT_SCHEMA})
      .then(v => ({...f, verdict: v}))
  ))
)
return { confirmed: results.flat().filter(Boolean).filter(f => f.verdict?.isReal) }
```

| Peça | O que faz |
|---|---|
| `meta` | nome, descrição e fases; o nome batiza a pasta do batch |
| `args` | o JSON de `--args`, ou `undefined` |
| `phase(título)` | agrupa os `agent()` seguintes no progresso |
| `agent(prompt, opts)` | dispara `run.sh` e espera com `wait.sh`; devolve o texto da resposta, ou o objeto validado com `schema` |
| `parallel(thunks)` | roda `() => ...` juntos; barreira; a que falha vira `null` |
| `pipeline(itens, etapa1, etapa2, ...)` | cada item atravessa as etapas sem barreira; etapa recebe `(anterior, item, índice)`; a que falha leva o item a `null` |

Opções de `agent`: `label`, `phase`, `schema`, `model`, `mode`, `base`, e uma extensão deste runner, `out` (veja Encadear). `mode: 'dangerous'` é recusado. Qualquer outra opção (`isolation`, `effort`, `agentType`) e qualquer outra função do Claude (`log`, `workflow`, `budget`) param o batch cedo, com saída 2. Não há resume nesta versão.

## schema

O `devin -p` não tem saída estruturada. O batch anexa ao prompt a instrução de responder com um bloco de código `json` que obedeça ao schema, extrai o **último** bloco e valida. Vale `type`, `required`, `properties`, `items` e `enum`; as outras palavras-chave do schema são ignoradas com um aviso. JSON ausente ou inválido falha a etapa (sem nova tentativa).

## Paralelismo

`--max N` (padrão `DEVIN_BATCH_MAX`, 3) limita os Devins ao mesmo tempo em todo o script; o resto espera na fila. Os Devins gastam cota: comece pequeno.

## Encadear

Cada `agent()` roda num worktree próprio, partindo de `HEAD` (ou de `base`). Uma etapa só enxerga o trabalho de outra pelo `base`, e só do que foi **commitado**: peça no prompt para commitar.

- Com `schema`, o objeto devolvido carrega `branch` e `runId` como propriedades não enumeráveis (somem num `{...x}`: copie antes).
- Sem `schema`, o retorno é texto: passe `out: obj` e leia `obj.branch` e `obj.id`.

```js
const a = await agent('Implemente X e commite.', {label: 'x', schema: S})
const b = await agent('Revise o que está no branch e commite correções.', {base: a.branch, label: 'revisa'})
```

Em `parallel` saem N branches independentes. **O batch não integra nada**: escolher, mesclar e limpar (`review.sh`, `clean.sh`) é com você.

## Estado e falhas

Em `$DEVIN_RUNS_DIR/batches/<id>/`: `script.mjs` (cópia), `journal.jsonl` (um evento por linha) e `result.json` (resultado, falhas, rodadas, pico de paralelismo). As rodadas são as de sempre (`check.sh`).

Uma etapa que falha vira `null` dentro de `parallel` e `pipeline`, como no Claude, mas o batch sai com 1 e imprime o resultado mesmo assim, com as falhas em `result.json`. Erro de configuração do script (opção ou função desconhecida) derruba tudo com 2. Ctrl-C ou `kill` no batch para de esperar, mas os Devins já disparados seguem; ache-os com [check](check.md).
