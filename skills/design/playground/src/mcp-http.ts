/**
 * O MCP por Streamable HTTP em /mcp, no mesmo Bun.serve da Web (CONTRATO.md,
 * "Os motores e os transportes"): um transporte e um McpServer por sessão,
 * guardados pelo mcp-session-id; DELETE /mcp fecha a sessão.
 *
 * A guarda (contra DNS rebinding): o Host precisa ser 127.0.0.1, localhost, o
 * IP da tailnet ou um nome *.ts.net (com ou sem porta); o Origin, quando vem,
 * do mesmo conjunto; senão 403. Com DP_TOKEN, exige Authorization: Bearer.
 *
 * O motor único entre as sessões (e o stdio) fica no Chat: aqui cada sessão
 * só entra com o transporte "http" e o tempo ocioso.
 */
import { timingSafeEqual } from "node:crypto";
import { existsSync } from "node:fs";
import type { Server } from "bun";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { log } from "./tipos.ts";

export const ROTA_MCP = "/mcp";
/** Quanto uma sessão HTTP fica sem chamar nada antes de soltar o motor. */
export const OCIOSO_MS = 120_000;

const IPV4 = /^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/;
const NOME_TS_NET = /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+ts\.net$/;

// ---------- a tailnet ----------

/**
 * O IP da tailnet em que o HTTP também escuta, ou null (só loopback).
 * DP_TAILNET=0 desliga; DP_TAILNET_IP manda; senão pergunta ao `tailscale ip -4`
 * (no PATH, ou o do app no macOS). Nunca devolve 0.0.0.0 nem loopback.
 */
export function resolverTailnet(env: Record<string, string | undefined> = process.env): string | null {
  if (env.DP_TAILNET === "0") return null;
  const valido = (ip: string | undefined): ip is string => !!ip && IPV4.test(ip) && ip !== "0.0.0.0" && !ip.startsWith("127.");
  if (env.DP_TAILNET_IP !== undefined) {
    const ip = env.DP_TAILNET_IP.trim();
    if (valido(ip)) return ip;
    log(`DP_TAILNET_IP inválido (${JSON.stringify(env.DP_TAILNET_IP)}): só loopback`);
    return null;
  }
  const candidatos = [Bun.which("tailscale"), "/Applications/Tailscale.app/Contents/MacOS/Tailscale"].filter(
    (c): c is string => !!c && existsSync(c),
  );
  for (const comando of candidatos) {
    try {
      const r = Bun.spawnSync([comando, "ip", "-4"], { stdin: "ignore", stdout: "pipe", stderr: "ignore", timeout: 3000 });
      if (r.exitCode !== 0) continue;
      const ip = r.stdout.toString().split("\n").map((l) => l.trim()).find(valido);
      if (ip) return ip;
    } catch {
      // tenta o próximo
    }
  }
  return null;
}

// ---------- a guarda ----------

/** O nome de um Host (sem a porta), em minúsculas; null se malformado. */
function nomeDoHost(host: string): string | null {
  const h = host.trim().toLowerCase();
  if (h.startsWith("[")) return null; // IPv6: não escutamos em nenhum
  const m = /^([^:]+)(?::(\d{1,5}))?$/.exec(h);
  return m ? m[1]! : null;
}

export type Guarda = {
  /** null se a requisição passa; senão a resposta de recusa. */
  conferir: (req: Request) => Response | null;
};

export function criarGuarda(opcoes: { tailnetIp?: string | null; token?: string }): Guarda {
  const fixos = new Set(["127.0.0.1", "localhost"]);
  if (opcoes.tailnetIp) fixos.add(opcoes.tailnetIp);
  const permitido = (nome: string | null) => !!nome && (fixos.has(nome) || NOME_TS_NET.test(nome));
  const token = opcoes.token ? Buffer.from(opcoes.token) : null;

  const recusar = (status: number, mensagem: string) =>
    Response.json({ jsonrpc: "2.0", error: { code: -32000, message: mensagem }, id: null }, { status });

  return {
    conferir(req) {
      const host = req.headers.get("host");
      if (!host || !permitido(nomeDoHost(host))) return recusar(403, `Host não permitido: ${host ?? "(nenhum)"}`);
      const origem = req.headers.get("origin");
      if (origem !== null) {
        let nome: string | null = null;
        try {
          const u = new URL(origem);
          if (u.protocol === "http:" || u.protocol === "https:") nome = u.hostname.toLowerCase();
        } catch {
          nome = null;
        }
        if (!permitido(nome)) return recusar(403, `Origin não permitida: ${origem}`);
      }
      if (token) {
        const m = /^Bearer\s+(.+)$/i.exec(req.headers.get("authorization") ?? "");
        const veio = m ? Buffer.from(m[1]!.trim()) : null;
        if (!veio || veio.length !== token.length || !timingSafeEqual(veio, token)) {
          return new Response(JSON.stringify({ jsonrpc: "2.0", error: { code: -32001, message: "token ausente ou errado (Authorization: Bearer <DP_TOKEN>)" }, id: null }), {
            status: 401,
            headers: { "content-type": "application/json", "www-authenticate": 'Bearer realm="design-playground"' },
          });
        }
      }
      return null;
    },
  };
}

// ---------- as sessões ----------

type Sessao = { transporte: WebStandardStreamableHTTPServerTransport; mcp: McpServer; getsAbertos: number; adeus?: ReturnType<typeof setTimeout> };

/**
 * Quanto esperar, depois que o GET de notificações de uma sessão cai, antes de fechar a sessão.
 * Um cliente que sai sem DELETE (o processo acabou) derruba esse GET: assim a vaga de motor se
 * solta em segundos, e não só pelo tempo ocioso. A espera cobre a reconexão do próprio cliente.
 */
export const ADEUS_MS = 3_000;

export type McpHttp = {
  /** Atende /mcp (POST, GET, DELETE). */
  tratar: (req: Request, servidor: Server<unknown>) => Promise<Response>;
  /** Quantas sessões HTTP estão abertas. */
  readonly sessoes: number;
  /** Fecha todas as sessões (ao encerrar). */
  fechar: () => Promise<void>;
};

export function criarMcpHttp(opcoes: { criarMcp: () => McpServer; guarda: Guarda; adeusMs?: number }): McpHttp {
  const adeusMs = opcoes.adeusMs ?? ADEUS_MS;
  const sessoes = new Map<string, Sessao>();

  const erroRpc = (status: number, code: number, message: string) =>
    Response.json({ jsonrpc: "2.0", error: { code, message }, id: null }, { status });

  async function novaSessao(req: Request): Promise<Response> {
    const transporte = new WebStandardStreamableHTTPServerTransport({
      sessionIdGenerator: () => crypto.randomUUID(),
      onsessioninitialized: (id) => {
        sessoes.set(id, { transporte, mcp, getsAbertos: 0 });
        log(`sessão MCP por HTTP aberta: ${id}`);
      },
    });
    // Antes do connect: o Protocol encadeia este onclose com o dele.
    transporte.onclose = () => {
      const id = transporte.sessionId;
      if (id && sessoes.delete(id)) log(`sessão MCP por HTTP fechada: ${id}`);
    };
    const mcp = opcoes.criarMcp();
    await mcp.connect(transporte);
    const resposta = await transporte.handleRequest(req);
    // Não era um initialize (o transporte já respondeu 400): nada fica aberto.
    if (!transporte.sessionId) await mcp.close().catch(() => {});
    return resposta;
  }

  /** O GET de notificações aberto; quando o último cai, a sessão fecha depois de `adeusMs`. */
  function vigiarGet(id: string, sessao: Sessao, req: Request): void {
    sessao.getsAbertos++;
    if (sessao.adeus) clearTimeout(sessao.adeus);
    sessao.adeus = undefined;
    req.signal.addEventListener("abort", () => {
      sessao.getsAbertos = Math.max(0, sessao.getsAbertos - 1);
      if (sessao.getsAbertos > 0) return;
      sessao.adeus = setTimeout(() => {
        sessao.adeus = undefined;
        if (sessao.getsAbertos > 0 || sessoes.get(id) !== sessao) return;
        log(`o GET da sessão ${id} caiu e não voltou: fecho a sessão`);
        sessoes.delete(id);
        sessao.mcp.close().catch((e) => log("erro ao fechar a sessão HTTP", e));
      }, adeusMs);
      sessao.adeus.unref?.();
    }, { once: true });
  }

  return {
    async tratar(req, servidor) {
      const recusa = opcoes.guarda.conferir(req);
      if (recusa) return recusa;
      // O chat_aguardar e o GET de notificações ficam abertos: sem o tempo ocioso do Bun.serve.
      servidor.timeout(req, 0);
      const id = req.headers.get("mcp-session-id");
      if (id) {
        const sessao = sessoes.get(id);
        if (!sessao) return erroRpc(404, -32001, "sessão não encontrada: comece outra com initialize");
        if (req.method === "GET") vigiarGet(id, sessao, req);
        return sessao.transporte.handleRequest(req);
      }
      if (req.method === "POST") return novaSessao(req);
      if (req.method === "GET" || req.method === "DELETE") return erroRpc(400, -32000, "falta o cabeçalho mcp-session-id");
      return new Response(null, { status: 405, headers: { allow: "GET, POST, DELETE" } });
    },
    get sessoes() {
      return sessoes.size;
    },
    async fechar() {
      const todas = [...sessoes.values()];
      sessoes.clear();
      await Promise.all(todas.map((s) => s.mcp.close().catch((e) => log("erro ao fechar a sessão HTTP", e))));
    },
  };
}
