/**
 * Entrada.
 *
 *   bun run src/main.ts              o MCP por stdio e o HTTP (a Web e o /mcp)
 *   bun run src/main.ts --servidor   só o HTTP (a Web e o /mcp), até SIGTERM/SIGINT
 *
 * O HTTP escuta em 127.0.0.1:$PORT (padrão 5317) e, se houver tailnet, também
 * no IP dela, na mesma porta. O stdout é só do MCP; todo log vai para o stderr.
 *
 * Variáveis: PORT, DADOS_DIR, ABRIR_WEB=0 (não abre o navegador),
 * DP_TAILNET=0 (só loopback), DP_TAILNET_IP (o IP da tailnet, sem perguntar ao
 * tailscale), DP_TOKEN (o /mcp exige Authorization: Bearer <DP_TOKEN>).
 */
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { criarApp, PORTA_PADRAO } from "./app.ts";
import { resolverTailnet } from "./mcp-http.ts";
import { log } from "./tipos.ts";

const servidor = process.argv.slice(2).includes("--servidor");

const porta = process.env.PORT ? Number(process.env.PORT) : PORTA_PADRAO;
if (!Number.isInteger(porta) || porta < 0 || porta > 65535) {
  log(`PORT inválida: ${process.env.PORT}`);
  process.exit(1);
}

const app = criarApp({
  porta,
  dadosDir: process.env.DADOS_DIR || undefined,
  abrirWeb: process.env.ABRIR_WEB !== "0",
  tailnetIp: resolverTailnet(),
  token: process.env.DP_TOKEN || undefined,
});

if (servidor && app.portaOcupada) {
  log(`modo servidor: a porta ${porta} já está em uso (outro motor em ${app.url}); saindo`);
  await app.parar();
  process.exit(1);
}

let mcp: McpServer | null = null;
let encerrando = false;
async function encerrar(motivo: string, codigo = 0): Promise<void> {
  if (encerrando) return;
  encerrando = true;
  log("encerrando:", motivo);
  // Garante que nada fica pendurado se algo travar.
  setTimeout(() => process.exit(codigo), 3000).unref();
  try {
    await mcp?.close(); // fecha o transporte → motor "sem-agente" no SSE
  } catch (erro) {
    log("erro ao fechar o MCP", erro);
  }
  try {
    await app.parar();
  } catch (erro) {
    log("erro ao parar", erro);
  }
  process.exit(codigo);
}

process.on("SIGTERM", () => void encerrar("SIGTERM"));
process.on("SIGINT", () => void encerrar("SIGINT"));
process.on("SIGHUP", () => void encerrar("SIGHUP"));

if (servidor) {
  log("modo servidor: sem stdio; o MCP está em", `${app.url}/mcp`);
} else {
  mcp = app.criarMcp();
  const transporte = new StdioServerTransport();
  transporte.onclose = () => void encerrar("transporte fechado");
  process.stdin.on("end", () => void encerrar("stdin fechado"));
  process.stdin.on("close", () => void encerrar("stdin fechado"));
  await mcp.connect(transporte);
  log("MCP pronto no stdio");
}
