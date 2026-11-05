# Lente "App Layer" para comparar frameworks de agente

Qualquer framework de agente (Hermes, pi/pi-durable, OpenClaw, DSPy, Pydantic AI, Vercel AI SDK, CrewAI, smolagents, Prime Agent...) implementa um subconjunto da mesma camada de aplicação: o estado que a app possui em volta do loop do modelo. Modele como a tupla

    A = (S, E, δ, π, ω, ρ, φ, T, Σ)

| Símbolo | Nome | Pergunta |
|---|---|---|
| S | Estado da app | Que estado tipado a APP possui (não o modelo)? Unidade, tipo, escopo (sessão/conversa/tarefa/run). |
| E | Log de eventos | O registro do que aconteceu: entries, mensagens, steps. Append-only? Tipos? |
| δ | Transição / commit | Como o estado muda? Atômico com o transcript? Quem escreve (tool, app, hook)? |
| π | Projeção ao modelo | Como o estado vira contexto: sections, Signature, instructions, memória, compactação. |
| ω | Observação | Como cliente/UI vê estado e progresso: stream, watch, multi-cliente. |
| ρ | Recuperação | Checkpoint, resume após crash, política de replay de tool, idempotência, storage. |
| φ | Fork / time travel | Dá para bifurcar, voltar, ler "as of"? |
| T | Tools e extensões | Definição de tool, registry/plugin, chamadas aninhadas, MCP. |
| Σ | Contrato tipado | I/O tipado app↔modelo: schemas de saída, signatures, validação, retry. |

Para cada símbolo: presente (sim/parcial/não), o nome real da API, um trecho real da fonte com URL, uma linha sobre a escolha de design. Nunca inventar API; "não achei" com onde procurou.

## Referência já lida: pi-durable (earendil-works/pi, `packages/durable`)

- Harness (um storage aberto + uma linha de commits atômicos; nada aparece antes de gravado), Conversation (transcript, `root()`, fork), Entry (`pi.user`, `pi.assistant`, `pi.tool-result`, `pi.system`, `pi.reset`), Commit (`conversation.commit(tx => …)`: entries + documentos + tasks, tudo ou nada), Task (máquina de estado durável, checkpoint por passo), Submission (`requestId` deduplica).
- Document = o domínio da app: `defineDoc({kind, version, scope: session|conversation|task, history: latest|rewindable, fork: initial|current|asOf, initial, migrate?, checkpointWhen})`, e `defineDocFamily` (com `initial(seed)`), em `src/types.ts` e `src/documents.ts`. Escrita com `tx.doc(Token, id)`; leitura `harness.snapshot`, `snapshotAsOf`, `watchDoc`; `persistence: {kind: "deferred", withinMs}` para progresso barato de perder. Os docs internos do próprio Pi usam o mesmo mecanismo: `pi.agent`, `pi.provider`, `pi.live`, `pi.inbox`, `pi.usage`.
- π: `section(key, render)` lê documentos e entra no system prompt antes de cada pedido. Tool: `defineTool({parameters, execute(args, api, ctx)})`, `replay: "safe"|"unsafe"` (padrão unsafe), `api.commit`, `api.executeTool` (aninhada, com key para replay).
- Exemplo executável que mostra tudo junto: `test/examples/10-extension-state.ts`. Adaptadores: Vercel `durable-harness`, Cloudflare `PiHarness` (Durable Object).
