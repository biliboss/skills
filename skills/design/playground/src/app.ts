/**
 * Monta o app: o estado do chat, o espelho do canvas, os componentes, o HTTP
 * (a Web e o MCP por Streamable HTTP em /mcp) e a fábrica do servidor MCP.
 * O main.ts liga isto ao stdio (ou só ao HTTP, com --servidor); os testes
 * sobem em porta aleatória (`porta: 0`) e ligam o MCP por InMemoryTransport.
 */
import { join } from "node:path";
import type { Server } from "bun";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { Canvas } from "./canvas.ts";
import { Chat } from "./chat.ts";
import { Componentes } from "./componentes.ts";
import { PatchesDoDisco } from "./patches-disco.ts";
import { criarMcp as criarServidorMcp } from "./ferramentas.ts";
import { criarRotas } from "./http.ts";
import { criarGuarda, criarMcpHttp, OCIOSO_MS, ROTA_MCP, type McpHttp } from "./mcp-http.ts";
import { Operacoes } from "./operacoes.ts";
import { log } from "./tipos.ts";

export const PORTA_PADRAO = 5317;
export const HOST = "127.0.0.1";

export type OpcoesApp = {
  /** 0 = porta aleatória. Padrão 5317. */
  porta?: number;
  /** Onde ficam conversa.jsonl, canvas.json e componentes/. Padrão <projeto>/dados. */
  dadosDir?: string;
  /** Pastas de patches (padrão: PATCHES_DIRS, ou $DESIGN_PRODUTOS/<produto>/patches). */
  patchesDirs?: string[];
  /** Padrão <projeto>/web. */
  webDir?: string;
  /** Abrir o navegador na primeira ferramenta / em web_abrir. Padrão true. */
  abrirWeb?: boolean;
  /** Intervalo do `: ping` do SSE. Padrão 15 s. */
  pingMs?: number;
  /** Intervalo do notifications/progress do chat_aguardar. Padrão 15 s. */
  progressoMs?: number;
  /** Quanto uma operação do canvas espera a página. Padrão 15 s. */
  operacaoMs?: number;
  /** Também escuta neste IP (o da tailnet), na mesma porta. Padrão: só 127.0.0.1. */
  tailnetIp?: string | null;
  /** Se vier, o /mcp exige Authorization: Bearer <token>. */
  token?: string;
  /** Quanto uma sessão HTTP fica sem chamar nada antes de soltar o motor. Padrão 120 s. */
  motorOciosoMs?: number;
  /** Depois que o GET de notificações de uma sessão HTTP cai, quanto esperar para fechá-la. Padrão 3 s. */
  adeusMs?: number;
};

export type App = {
  chat: Chat;
  canvas: Canvas;
  operacoes: Operacoes;
  componentes: Componentes;
  /** null quando a porta já estava em uso (outra sessão é o motor). */
  http: Server<unknown> | null;
  /** O segundo Bun.serve, no IP da tailnet; null sem tailnet ou se não deu para escutar lá. */
  httpTailnet: Server<unknown> | null;
  mcpHttp: McpHttp;
  porta: number;
  url: string;
  /** Onde o HTTP escuta de fato ("http://ip:porta"). */
  enderecos: string[];
  portaOcupada: boolean;
  /** Um McpServer novo, ligado a este app, para o stdio (ou um teste). Conecte-o a um transporte. */
  criarMcp: () => McpServer;
  /** Para o HTTP, fecha as sessões, solta as esperas e grava o que falta. */
  parar: () => Promise<void>;
};

const RAIZ = join(import.meta.dir, "..");

function portaEmUso(erro: unknown): boolean {
  const e = erro as { code?: string; message?: string } | undefined;
  return e?.code === "EADDRINUSE" || /EADDRINUSE|address already in use|in use/i.test(e?.message ?? "");
}

function abrirNoNavegador(url: string): boolean {
  const comando =
    process.platform === "darwin" ? ["open", url] : process.platform === "win32" ? ["cmd", "/c", "start", "", url] : ["xdg-open", url];
  try {
    // stdout ignorado: o stdout do processo é só do MCP.
    Bun.spawn(comando, { stdin: "ignore", stdout: "ignore", stderr: "ignore" }).unref();
    log("abri a Web em", url);
    return true;
  } catch (erro) {
    log("não consegui abrir o navegador", erro);
    return false;
  }
}

export function criarApp(opcoes: OpcoesApp = {}): App {
  const portaPedida = opcoes.porta ?? PORTA_PADRAO;
  const dadosDir = opcoes.dadosDir ?? join(RAIZ, "dados");
  const webDir = opcoes.webDir ?? join(RAIZ, "web");
  const deveAbrir = opcoes.abrirWeb ?? true;
  const tailnetIp = opcoes.tailnetIp ?? null;

  const chat = new Chat(dadosDir);
  const canvas = new Canvas(dadosDir);
  const operacoes = new Operacoes(chat, opcoes.operacaoMs);
  const componentes = new Componentes(dadosDir, opcoes.patchesDirs ? new PatchesDoDisco(() => opcoes.patchesDirs!) : undefined);
  // Cada definição avisa todas as abas: elas buscam a definição nova e redesenham as instâncias.
  componentes.aoDefinir = (c) => chat.transmitir({ tipo: "componente", dados: { id: c.id, versao: c.versao } });
  const { rota, fecharEventos } = criarRotas({ chat, canvas, operacoes, componentes, webDir, pingMs: opcoes.pingMs });

  // Preenchidos logo abaixo; a fábrica do MCP só é chamada depois.
  let url = "";
  let portaOcupada = false;
  const abrirWeb = () => (deveAbrir ? abrirNoNavegador(url) : false);
  const fabrica = (transporte: string, ociosoMs?: number) =>
    criarServidorMcp({
      chat,
      operacoes,
      componentes,
      canvas,
      url,
      portaOcupada,
      abrirWeb,
      progressoMs: opcoes.progressoMs,
      transporte,
      ociosoMs,
    });

  const mcpHttp = criarMcpHttp({
    criarMcp: () => fabrica("http", opcoes.motorOciosoMs ?? OCIOSO_MS),
    guarda: criarGuarda({ tailnetIp, token: opcoes.token }),
    adeusMs: opcoes.adeusMs,
  });

  const fetch = (req: Request, servidor: Server<unknown>): Promise<Response> => {
    const { pathname } = new URL(req.url);
    if (pathname === ROTA_MCP) {
      return mcpHttp.tratar(req, servidor).catch((e) => {
        log("erro no /mcp", e);
        return Response.json({ jsonrpc: "2.0", error: { code: -32603, message: "erro interno" }, id: null }, { status: 500 });
      });
    }
    return rota(req, servidor);
  };

  let http: Server<unknown> | null = null;
  try {
    http = Bun.serve({ hostname: HOST, port: portaPedida, fetch });
  } catch (erro) {
    if (!portaEmUso(erro)) throw erro;
    portaOcupada = true;
    log(`a porta ${portaPedida} já está em uso: outra sessão é o motor; as ferramentas vão recusar`);
  }

  const porta = http?.port ?? portaPedida;
  url = `http://${HOST}:${porta}`;
  const enderecos: string[] = [];

  let httpTailnet: Server<unknown> | null = null;
  if (http) {
    enderecos.push(url);
    if (tailnetIp) {
      try {
        httpTailnet = Bun.serve({ hostname: tailnetIp, port: porta, fetch });
        enderecos.push(`http://${tailnetIp}:${porta}`);
      } catch (erro) {
        log(`não consegui escutar na tailnet (${tailnetIp}:${porta}); só loopback:`, erro instanceof Error ? erro.message : erro);
      }
    }
    log("escutando em", enderecos.join(" e "), "· MCP em", `${url}${ROTA_MCP}`, "· dados em", dadosDir);
  }

  return {
    chat,
    canvas,
    operacoes,
    componentes,
    http,
    httpTailnet,
    mcpHttp,
    porta,
    url,
    enderecos,
    portaOcupada,
    criarMcp: () => fabrica("stdio"),
    parar: async () => {
      chat.soltarEsperas();
      operacoes.soltar();
      await mcpHttp.fechar();
      fecharEventos();
      await Bun.sleep(50); // deixa o último evento (motor "sem-agente") sair
      await Promise.all([http?.stop(true), httpTailnet?.stop(true)]);
      await Promise.all([chat.descarregar(), canvas.descarregar()]);
    },
  };
}
