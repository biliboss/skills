# design-playground

Um MCP e uma Web: um canvas do tldraw no centro e um chat à direita. Não há LLM no servidor. O agente que instala o MCP (Claude Code ou pi) abre a Web e vira o motor dela: a pessoa escreve no chat, o agente recebe por `chat_aguardar` e responde por `chat_responder`. O plano, as ferramentas de depois (o canvas) e as perguntas abertas estão em [`.wiki/design-playground.md`](../../.wiki/design-playground.md). As interfaces internas estão em [CONTRATO.md](CONTRATO.md).

## Rodar

```sh
bun install
bun test                 # 44 testes: HTTP, SSE, espera longa, ferramentas, canvas, atividade, persistência, segunda sessão, stdio
```

O processo sobe pelo agente, não à mão:

- **Claude Code:** `claude mcp add design-playground -- bun run /Users/billiboss/biliboss/dev/design-playground/src/main.ts`
- **pi:** em `~/.pi/agent/mcp.json`, com `idleTimeout: 0` (sobe na primeira chamada e não cai no ocioso, que levaria a Web junto; o adapter ignora `lifecycle`):

```json
"design-playground": {
  "command": "bun",
  "args": ["run", "/Users/billiboss/biliboss/dev/design-playground/src/main.ts"],
  "idleTimeout": 0
}
```

Depois, peça ao agente: "seja o motor do design-playground". Ele chama `web_abrir` (abre `http://127.0.0.1:5317`) e fica em `chat_aguardar`.

## Ferramentas

`web_abrir`, `chat_aguardar`, `chat_responder`, `chat_digitando`, `chat_historico`, `chat_atividade` (a linha de atividade), `chat_apagar`, `tela_criar`, `tela_mudar`, `tela_ler`, `canvas_ler`, `canvas_criar`, `canvas_mudar`, `canvas_apagar`, `canvas_focar`. As do canvas vão à página aberta pelo SSE (`canvas`), o editor do tldraw aplica e responde em `POST /api/canvas/resposta`; sem página aberta, recusam na hora.

## Variáveis

| Variável | Padrão | O quê |
|---|---|---|
| `PORT` | `5317` | A porta da Web. Uma segunda sessão na mesma porta recebe erro em toda ferramenta. |
| `DADOS_DIR` | `./dados` | `conversa.jsonl` e `canvas.json` (fora do git). |
| `ABRIR_WEB` | `1` | `0` não abre o navegador (testes). |

## Partes

- `src/main.ts`: o MCP por stdio e o HTTP no mesmo processo; `src/app.ts` monta tudo (`criarApp`), `src/chat.ts` o estado e a espera longa, `src/http.ts` as rotas e o SSE, `src/canvas.ts` o espelho do canvas, `src/ferramentas.ts` as ferramentas e as instruções.
- `web/index.html` e `web/app.css`: o layout; `web/canvas.js`: o tldraw 3.15.4 (esm.sh, sem build); `web/chat.js` e `web/chat.css`: o chat (marked 18.1.3 e DOMPurify 3.4.17).

O tldraw mostra a marca "Made with tldraw" sem licença; para uso local, tudo bem.
